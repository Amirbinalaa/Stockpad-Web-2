from . import serializers
from rest_framework import generics, status, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models, transaction
from django.db.models import Q, Sum, Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from decimal import Decimal
import uuid
import requests
import logging
import hmac
import hashlib
import os
import json
from concurrent.futures import ThreadPoolExecutor

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .site_a_client import submit_request_to_site_a, SiteAError, fetch_wm_catalog_for_engineer, check_engineer_status_on_wm

logger = logging.getLogger('api')

# Module-level thread pool — reused across all requests, avoids per-request thread overhead.
_site_a_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="site_a_sync")


def _sync_to_site_a(request_id, material_site_a_id, requester_email, quantity, reason):
    """
    Background worker: calls the WM Website and updates the local MaterialRequest with the result.
    Runs in a thread-pool thread so the HTTP response is never blocked by WM Website latency.

    Args:
        request_id:        Local MaterialRequest PK — used to write back the result.
        material_site_a_id: The WM Website's own material ID (Material.site_a_material_id).
        requester_email:   Engineer's email — forwarded to WM so managers know who requested.
        quantity:          Quantity being requested.
        reason:            Free-text justification (maps to MaterialRequest.justification).
    """
    from django.db import connection
    try:
        site_a_response = submit_request_to_site_a(
            material_id=material_site_a_id,
            quantity=quantity,
            requester_email=requester_email,
            justification=reason,
        )
        # Use .filter().update() — safe from any thread, avoids stale-object issues.
        from .models import MaterialRequest
        MaterialRequest.objects.filter(pk=request_id).update(
            site_a_request_id=site_a_response["id"],
            sync_status='synced',
        )
        logger.info(f"[BG] Request {request_id} synced to WM Website (WM ID: {site_a_response['id']}).")
    except (SiteAError, requests.exceptions.RequestException) as e:
        from .models import MaterialRequest
        MaterialRequest.objects.filter(pk=request_id).update(sync_status='sync_failed')
        logger.error(f"[BG] Failed to sync request {request_id} to WM Website: {e}")
    finally:
        # Each thread-pool thread holds its own DB connection; close it to prevent pool exhaustion.
        connection.close()


from .models import (
    User, Material, MaterialRequest, Category,
    Product, BOMItem, ProductionPlan, ProductionPlanItem, MaterialRequirement,
    Supplier, ProcurementRequest, ProcurementOrder, RequestStatusHistory,
    ChatMessage, ChatConversation,
)
from .serializers import (
    UserSerializer, RegisterSerializer, EmailTokenObtainPairSerializer,
    MaterialSerializer, MaterialListSerializer, MaterialRequestSerializer,
    CategorySerializer, RequestStatusHistorySerializer,
    ProductSerializer, BOMItemSerializer, ProductionPlanSerializer,
    ProductionPlanItemSerializer, MaterialRequirementSerializer,
    SupplierSerializer, ProcurementRequestSerializer, ProcurementOrderSerializer,
    ChatMessageSerializer, ChatConversationSerializer,
)
from .permissions import IsOwnerOrStaff
from .chatbot_logic import InventoryChatBot, load_data_professional_from_file
from rest_framework_simplejwt.views import TokenObtainPairView


# ─────────────────────────────────────────────
# AUTH VIEWS
# ─────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = EmailTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer


class UserMeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class LogoutView(APIView):
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """Allow authenticated users to change their password."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not old_password or not new_password:
            return Response({'error': 'old_password and new_password are required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not request.user.check_password(old_password):
            return Response({'error': 'Old password is incorrect.'},
                            status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.save()
        return Response({'message': 'Password changed successfully.'})


# ─────────────────────────────────────────────
# CATEGORY VIEWS
# ─────────────────────────────────────────────

class CategoryViewSet(viewsets.ModelViewSet):
    """Full CRUD for Categories with material count."""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']


# ─────────────────────────────────────────────
# MATERIAL VIEWS
# ─────────────────────────────────────────────

class MaterialViewSet(viewsets.ModelViewSet):
    """Full CRUD for Materials with filtering, searching, low-stock and stock-status actions."""
    queryset = Material.objects.select_related('category').all()
    serializer_class = MaterialSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'status', 'unit']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'quantity_available', 'unit_cost', 'last_updated']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return MaterialListSerializer
        return MaterialSerializer

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Return materials whose quantity_available <= min_stock_level."""
        from django.db.models import F as _F
        qs = self.get_queryset().filter(quantity_available__lte=_F('min_stock_level'))
        serializer = MaterialListSerializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})

    @action(detail=True, methods=['get'])
    def stock_status(self, request, pk=None):
        """Detailed stock information for a single material."""
        material = self.get_object()
        return Response({
            'id': material.id,
            'name': material.name,
            'quantity_available': material.quantity_available,
            'min_stock_level': material.min_stock_level,
            'unit': material.unit,
            'status': material.status,
            'needs_reorder': material.needs_reorder,
            'stock_value': float(material.stock_value),
            'last_updated': material.last_updated,
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced search by name, code, description, category."""
        q = request.query_params.get('q', '').strip()
        category = request.query_params.get('category', '').strip()

        if not q or len(q) < 2:
            return Response({'error': 'Query must be at least 2 characters.'},
                            status=status.HTTP_400_BAD_REQUEST)

        qs = self.get_queryset().filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q)
        )
        if category:
            qs = qs.filter(category__name__icontains=category)

        serializer = MaterialListSerializer(qs, many=True)
        return Response({'query': q, 'count': qs.count(), 'results': serializer.data})


# ─────────────────────────────────────────────
# MATERIAL REQUESTS (engineer workflow)
# ─────────────────────────────────────────────

class CreateRequestView(generics.CreateAPIView):
    serializer_class = MaterialRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        material_request = serializer.save(requested_by=self.request.user)
        RequestStatusHistory.objects.create(
            request=material_request,
            old_status='',
            new_status='pending',
            changed_by=self.request.user,
            notes='Initial request created.'
        )

        # Fire-and-forget: submit to background thread and return immediately to the caller.
        logger.info(
            f"Dispatching WM Website sync for request {material_request.id} "
            f"(material: {material_request.material.name}) to background thread."
        )
        site_a_mat_id = material_request.material.site_a_material_id or material_request.material.id
        _site_a_executor.submit(
            _sync_to_site_a,
            material_request.id,
            site_a_mat_id,
            self.request.user.email,      # forwarded to WM so managers see who requested
            material_request.quantity_needed,
            material_request.justification,
        )


class MyRequestsView(generics.ListAPIView):
    serializer_class = MaterialRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MaterialRequest.objects.filter(requested_by=self.request.user).order_by('-request_date')


class MaterialRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Allow editing and deleting own pending requests."""
    serializer_class = MaterialRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MaterialRequest.objects.filter(requested_by=self.request.user)

    def perform_update(self, serializer):
        obj = self.get_object()
        if obj.status != 'pending':
            raise serializers.ValidationError("Only pending requests can be modified.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != 'pending':
            raise serializers.ValidationError("Only pending requests can be deleted.")
        instance.delete()


class AllRequestsView(generics.ListAPIView):
    serializer_class = MaterialRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = MaterialRequest.objects.all().order_by('-request_date')


@method_decorator(csrf_exempt, name='dispatch')
class SiteAWebhookView(APIView):
    permission_classes = [permissions.AllowAny]  # authenticated via HMAC, not session/JWT

    def post(self, request):
        import time as _time

        # ── Step 1: Require both security headers ────────────────────────────
        received_sig = request.headers.get("X-Webhook-Signature", "")
        received_ts  = request.headers.get("X-Webhook-Timestamp", "")

        if not received_sig or not received_ts:
            logger.warning(
                "Inbound webhook rejected: missing X-Webhook-Signature or "
                "X-Webhook-Timestamp header."
            )
            return HttpResponse(status=400)

        # ── Step 2: Replay-attack window (±5 minutes) ────────────────────────
        try:
            ts_int = int(received_ts)
        except ValueError:
            logger.warning("Inbound webhook rejected: X-Webhook-Timestamp is not a valid integer.")
            return HttpResponse(status=400)

        if abs(_time.time() - ts_int) > 300:
            logger.warning(
                f"Inbound webhook rejected: timestamp {received_ts} is outside the "
                "300-second replay-attack window."
            )
            return HttpResponse(status=403)

        # ── Step 3: HMAC-SHA256 signature verification ───────────────────────
        # WM Website signs:  HMAC-SHA256(secret, f"{timestamp}.{raw_json_body}")
        # We must reconstruct the exact same signing message.
        raw_body_str = request.body.decode("utf-8")
        signing_message = f"{received_ts}.{raw_body_str}".encode("utf-8")
        expected_sig = hmac.new(
            key=settings.WEBHOOK_SHARED_SECRET.encode("utf-8"),
            msg=signing_message,
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(received_sig, expected_sig):
            logger.warning("Inbound webhook rejected: HMAC signature mismatch.")
            return HttpResponse(status=403)

        # ── Step 4: Parse JSON payload ───────────────────────────────────────
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Inbound webhook rejected: payload is not valid JSON.")
            return HttpResponse(status=400)

        site_a_id  = payload.get("id")
        raw_status = payload.get("status")

        # ── Step 5: Map WM status values to our internal choices ─────────────
        # WM Website sends "approved" or "denied"; our MaterialRequest model
        # uses "approved" and "rejected" — map accordingly.
        STATUS_MAP = {"approved": "approved", "denied": "rejected"}
        new_status = STATUS_MAP.get(raw_status, raw_status)

        # ── Step 6: Persist the status update (idempotent) ───────────────────
        try:
            with transaction.atomic():
                material_request = MaterialRequest.objects.select_for_update().get(
                    site_a_request_id=site_a_id
                )
                if material_request.status != new_status:  # idempotency guard
                    old_status = material_request.status
                    material_request.status = new_status
                    material_request.save(update_fields=['status'])
                    RequestStatusHistory.objects.create(
                        request=material_request,
                        old_status=old_status,
                        new_status=new_status,
                        changed_by=None,
                        notes=f'Status updated via WM Website webhook (raw: "{raw_status}").',
                    )
                    logger.info(
                        f"Webhook: request {material_request.id} (WM ID: {site_a_id}) "
                        f"updated '{old_status}' → '{new_status}'."
                    )
                else:
                    logger.info(
                        f"Webhook: request {material_request.id} already has "
                        f"status '{new_status}' — no-op (idempotent)."
                    )
        except MaterialRequest.DoesNotExist:
            logger.warning(f"Webhook received for unknown WM request id={site_a_id}.")
            return HttpResponse(status=404)

        # Return 200 immediately so WM Website doesn't retry unnecessarily.
        return JsonResponse({"ok": True}, status=200)


# ─────────────────────────────────────────────
# WM SITE PROXY VIEWS  (Team Access Control Integration)
# ─────────────────────────────────────────────

class WMCatalogProxyView(APIView):
    """
    PE Backend proxy for the WM materials catalogue.

    GET /api/wm/catalog/

    Forwards the logged-in engineer’s email to the WM site so the WM server
    can filter and return only the materials belonging to the Warehouse Manager
    who has whitelisted this engineer.  The response is passed through verbatim
    so the frontend receives the same structure as a direct WM call.

    Using this backend proxy avoids browser CORS restrictions when the WM site
    is on a different origin from the PE frontend.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        engineer_email = (request.user.email or '').lower().strip()
        if not engineer_email:
            return Response(
                {'error': 'Engineer email not set on this account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            materials = fetch_wm_catalog_for_engineer(engineer_email)
            return Response(materials, status=status.HTTP_200_OK)
        except SiteAError as exc:
            logger.warning(f"[WM Catalog Proxy] WM error for {engineer_email}: {exc}")
            return Response(
                {'error': str(exc), 'source': 'wm_site'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            logger.error(f"[WM Catalog Proxy] Unexpected error: {exc}", exc_info=True)
            return Response(
                {'error': f'Unexpected error reaching WM site: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WMEngineerStatusView(APIView):
    """
    PE Backend proxy for the WM engineer whitelist status check.

    GET /api/wm/status/

    Returns { "connected": bool, "manager_name": str|null } so the PE Profile
    page can render the live connection badge without making a cross-origin
    call from the browser.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        engineer_email = (request.user.email or '').lower().strip()
        if not engineer_email:
            return Response({'connected': False, 'manager_name': None})
        try:
            result = check_engineer_status_on_wm(engineer_email)
            return Response(result, status=status.HTTP_200_OK)
        except SiteAError as exc:
            logger.warning(f"[WM Status Proxy] WM error for {engineer_email}: {exc}")
            return Response(
                {'connected': False, 'manager_name': None, 'error': str(exc)},
                status=status.HTTP_200_OK,   # return 200 so the badge renders, not an error page
            )
        except Exception as exc:
            logger.error(f"[WM Status Proxy] Unexpected error: {exc}", exc_info=True)
            return Response({'connected': False, 'manager_name': None, 'error': str(exc)})


# ─────────────────────────────────────────────
# INVENTORY SUMMARY  (dashboard)
# ─────────────────────────────────────────────

class InventorySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import F as _F
        total_materials = Material.objects.count()
        in_stock = Material.objects.filter(status='In Stock').count()
        low_stock = Material.objects.filter(status='Low Stock').count()
        out_of_stock = Material.objects.filter(status='Out of Stock').count()
        needs_reorder = Material.objects.filter(quantity_available__lte=_F('min_stock_level')).count()
        total_value = Material.objects.aggregate(
            val=Sum(
                _F('quantity_available') * _F('unit_cost')
            )
        )['val'] or 0

        pending_requests = MaterialRequest.objects.filter(status='pending').count()
        approved_requests = MaterialRequest.objects.filter(status='approved').count()

        return Response({
            'materials': {
                'total': total_materials,
                'in_stock': in_stock,
                'low_stock': low_stock,
                'out_of_stock': out_of_stock,
                'needs_reorder': needs_reorder,
                'total_inventory_value': float(total_value),
            },
            'requests': {
                'pending': pending_requests,
                'approved': approved_requests,
            },
            'categories': Category.objects.count(),
            'suppliers': Supplier.objects.filter(is_active=True).count(),
        })


# ─────────────────────────────────────────────
# DASHBOARD ANALYTICS
# ─────────────────────────────────────────────

class DashboardAnalyticsView(APIView):
    """Rich analytics data for the dashboard charts."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import F as _F
        from django.utils import timezone as tz
        from datetime import timedelta
        import calendar

        # ── Monthly requests – last 6 months ──────────────────────────────
        today = tz.now()
        monthly_labels = []
        monthly_counts = []
        for i in range(5, -1, -1):
            month_start = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
            last_day = calendar.monthrange(month_start.year, month_start.month)[1]
            month_end = month_start.replace(day=last_day, hour=23, minute=59, second=59)
            count = MaterialRequest.objects.filter(
                request_date__gte=month_start,
                request_date__lte=month_end
            ).count()
            monthly_labels.append(month_start.strftime('%b %Y'))
            monthly_counts.append(count)

        # ── Top 5 most-requested materials ────────────────────────────────
        top_materials_qs = (
            MaterialRequest.objects
            .values('material__name')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        )
        top_materials = [
            {'name': item['material__name'], 'count': item['total']}
            for item in top_materials_qs
        ]

        # ── Request Status Breakdown ───────────────────────────────────────
        status_breakdown = {
            'pending': MaterialRequest.objects.filter(status='pending').count(),
            'approved': MaterialRequest.objects.filter(status='approved').count(),
            'rejected': MaterialRequest.objects.filter(status='rejected').count(),
        }

        # ── Inventory Value By Category ────────────────────────────────────
        cat_values_qs = (
            Material.objects
            .values('category__name')
            .annotate(total_value=Sum(_F('quantity_available') * _F('unit_cost')))
            .order_by('-total_value')[:6]
        )
        cat_data = [
            {'category': item['category__name'] or 'Uncategorized', 'value': float(item['total_value'] or 0)}
            for item in cat_values_qs
        ]

        return Response({
            'monthly_requests': {
                'labels': monthly_labels,
                'data': monthly_counts,
            },
            'top_materials': top_materials,
            'status_breakdown': status_breakdown,
            'inventory_by_category': cat_data,
        })


# ─────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────

class NotificationsView(APIView):
    """Return recent request status changes for the current user."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Show last 20 status events for the current user's requests
        history_qs = (
            RequestStatusHistory.objects
            .filter(request__requested_by=request.user)
            .exclude(new_status='pending')  # skip the initial creation event
            .order_by('-changed_at')[:20]
        )

        notifications = []
        for h in history_qs:
            if h.new_status == 'approved':
                icon = 'check-circle'
                color = '#22c55e'
                text = f"Your request for {h.request.material.name} was Approved."
            elif h.new_status == 'rejected':
                icon = 'times-circle'
                color = '#ef4444'
                note = f" Reason: {h.notes}" if h.notes else ''
                text = f"Your request for {h.request.material.name} was Rejected.{note}"
            else:
                continue

            notifications.append({
                'id': h.id,
                'text': text,
                'icon': icon,
                'color': color,
                'time': h.changed_at.isoformat(),
                'status': h.new_status,
            })

        return Response({'notifications': notifications, 'count': len(notifications)})




# ─────────────────────────────────────────────
# BOM VIEWS
# ─────────────────────────────────────────────

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'category', 'created_at']
    ordering = ['category', 'name']

    def perform_create(self, serializer):
        serializer.save(id=f"PRD-{uuid.uuid4().hex[:8].upper()}")

    @action(detail=True, methods=['get'])
    def bom(self, request, pk=None):
        product = self.get_object()
        items = product.bom_items.filter(is_active=True)
        return Response(BOMItemSerializer(items, many=True).data)

    @action(detail=True, methods=['post'])
    def calculate_cost(self, request, pk=None):
        product = self.get_object()
        return Response({
            'product_id': product.id,
            'product_name': product.name,
            'estimated_cost_per_unit': float(product.estimated_cost_per_unit),
            'calculated_cost': round(product.calculated_cost, 2),
            'difference': round(product.calculated_cost - float(product.estimated_cost_per_unit), 2),
        })

    @action(detail=False, methods=['get'])
    def active(self, request):
        qs = self.get_queryset().filter(is_active=True)
        return Response(ProductSerializer(qs, many=True).data)


class BOMItemViewSet(viewsets.ModelViewSet):
    queryset = BOMItem.objects.select_related('product', 'material').all()
    serializer_class = BOMItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product', 'material', 'category', 'is_active']
    search_fields = ['material__name', 'category']
    ordering = ['category', 'material__name']


class ProductionPlanViewSet(viewsets.ModelViewSet):
    queryset = ProductionPlan.objects.all()
    serializer_class = ProductionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'description']
    ordering = ['-start_date']

    def perform_create(self, serializer):
        serializer.save(
            id=f"PP-{uuid.uuid4().hex[:8].upper()}",
            created_by=self.request.user
        )

    @action(detail=True, methods=['post'])
    def calculate_requirements(self, request, pk=None):
        plan = self.get_object()
        plan.requirements.all().delete()

        for plan_item in plan.plan_items.all():
            for bom_item in plan_item.product.bom_items.filter(is_active=True):
                material = bom_item.material
                required = (
                    Decimal(str(bom_item.quantity_per_unit)) *
                    Decimal(str(plan_item.quantity)) *
                    (1 + Decimal(str(bom_item.waste_factor)))
                )
                current = Decimal(str(material.quantity_available))
                shortage = max(Decimal('0'), required - current)
                unit_cost = material.unit_cost
                urgency = 'low'
                if shortage > 0:
                    if plan_item.priority in ['urgent', 'critical']:
                        urgency = 'critical'
                    elif plan_item.priority == 'high':
                        urgency = 'high'
                    else:
                        urgency = 'medium'

                MaterialRequirement.objects.update_or_create(
                    plan=plan, material=material,
                    defaults={
                        'total_required': required,
                        'current_stock': current,
                        'shortage': shortage,
                        'unit_cost': unit_cost,
                        'total_cost': required * unit_cost,
                        'shortage_value': shortage * unit_cost,
                        'urgency': urgency,
                    }
                )

        return Response({
            'message': 'Requirements calculated.',
            'total_requirements': plan.requirements.count(),
            'total_shortage_value': float(
                plan.requirements.aggregate(t=Sum('shortage_value'))['t'] or 0
            ),
        })

    @action(detail=True, methods=['get'])
    def shortages(self, request, pk=None):
        plan = self.get_object()
        qs = plan.requirements.filter(shortage__gt=0)
        return Response(MaterialRequirementSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def start_plan(self, request, pk=None):
        plan = self.get_object()
        if plan.status != 'planned':
            return Response({'error': 'Only planned plans can be started.'},
                            status=status.HTTP_400_BAD_REQUEST)
        plan.status = 'in_progress'
        plan.save()
        return Response({'message': 'Production plan started.', 'status': plan.status})

    @action(detail=True, methods=['post'])
    def complete_plan(self, request, pk=None):
        plan = self.get_object()
        if plan.status != 'in_progress':
            return Response({'error': 'Only in-progress plans can be completed.'},
                            status=status.HTTP_400_BAD_REQUEST)
        plan.status = 'completed'
        plan.save()
        return Response({'message': 'Production plan completed.', 'status': plan.status})


class ProductionPlanItemViewSet(viewsets.ModelViewSet):
    queryset = ProductionPlanItem.objects.all()
    serializer_class = ProductionPlanItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['plan', 'product', 'priority']
    ordering = ['priority', 'start_week']

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        item = self.get_object()
        completed = request.data.get('completed_quantity')
        if completed is None:
            return Response({'error': 'completed_quantity is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        item.completed_quantity = int(completed)
        item.save()
        return Response({
            'message': 'Progress updated.',
            'completed_quantity': item.completed_quantity,
            'completion_percentage': round(item.completion_percentage, 1),
        })


class MaterialRequirementViewSet(viewsets.ModelViewSet):
    queryset = MaterialRequirement.objects.all()
    serializer_class = MaterialRequirementSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['plan', 'material', 'urgency']
    ordering = ['-shortage_value']

    @action(detail=False, methods=['get'])
    def critical(self, request):
        qs = self.get_queryset().filter(urgency='critical')
        return Response(MaterialRequirementSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def shortages(self, request):
        qs = self.get_queryset().filter(shortage__gt=0)
        return Response(MaterialRequirementSerializer(qs, many=True).data)


# ─────────────────────────────────────────────
# SUPPLIER & PROCUREMENT VIEWS
# ─────────────────────────────────────────────

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'contact_person', 'email']
    ordering = ['-reliability_score', 'name']


class ProcurementRequestViewSet(viewsets.ModelViewSet):
    queryset = ProcurementRequest.objects.all()
    serializer_class = ProcurementRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'material']
    search_fields = ['material__name', 'notes']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        pr = self.get_object()
        if pr.status != 'draft':
            return Response({'error': 'Only draft requests can be submitted.'},
                            status=status.HTTP_400_BAD_REQUEST)
        pr.status = 'submitted'
        pr.submitted_at = timezone.now()
        pr.save()
        return Response({'message': 'Submitted.', 'status': pr.status})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        pr = self.get_object()
        if pr.status != 'submitted':
            return Response({'error': 'Only submitted requests can be approved.'},
                            status=status.HTTP_400_BAD_REQUEST)
        pr.status = 'approved'
        pr.approved_by = request.user
        pr.approved_at = timezone.now()
        pr.save()
        return Response({'message': 'Approved.', 'status': pr.status})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        pr = self.get_object()
        pr.status = 'rejected'
        pr.save()
        return Response({'message': 'Rejected.', 'status': pr.status})


class ProcurementOrderViewSet(viewsets.ModelViewSet):
    queryset = ProcurementOrder.objects.select_related('supplier').all()
    serializer_class = ProcurementOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'supplier']
    search_fields = ['supplier__name', 'notes', 'supplier_order_number']
    ordering = ['-order_date']


class RequestStatusHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit log for request status changes."""
    queryset = RequestStatusHistory.objects.all()
    serializer_class = RequestStatusHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['request', 'new_status']
    ordering = ['-changed_at']


# ─────────────────────────────────────────────
# CHATBOT VIEW  (Google Gemini + live DB data)
# ─────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")  # set via environment variable



class ChatbotView(APIView):
    """
    POST /api/chatbot/
    Body: { "message": "..." }
    Returns: { "reply": "..." }

    Fetches live inventory from PostgreSQL, injects it as context into a
    Gemini prompt, and streams back the AI's answer.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _build_inventory_context(self):
        """Build a compact markdown table of current inventory."""
        materials = Material.objects.select_related('category').all()
        lines = ["| Material | Category | Quantity | Unit | Status | Unit Cost |",
                 "|---|---|---|---|---|---|"]
        for m in materials:
            cat_name = m.category.name if m.category else "Uncategorized"
            lines.append(
                f"| {m.name} | {cat_name} | {m.quantity_available} | {m.unit} "
                f"| {m.status} | {m.unit_cost} |"
            )
        return "\n".join(lines)

    def post(self, request):
        user_message = request.data.get("message", "").strip()
        user_lang = request.data.get("lang", "en")
        conversation_id = request.data.get("conversation_id")
        
        if not user_message:
            return Response({"error": "Message is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Get or Create Conversation
            if conversation_id:
                conversation = ChatConversation.objects.get(id=conversation_id, user=request.user)
            else:
                # auto-title with first 50 chars of first message
                title = user_message[:50] + "..." if len(user_message) > 50 else user_message
                conversation = ChatConversation.objects.create(user=request.user, title=title)

            # 2. Fetch history for context (last 10 messages)
            history_qs = conversation.messages.all().order_by('timestamp')[:10]
            history_data = ChatMessageSerializer(history_qs, many=True).data

            # 3. Initialize Bot
            bot = InventoryChatBot(api_key=GEMINI_API_KEY)
            bot.inventory_data = self._build_inventory_context()
            
            # 4. Handle Files
            uploaded_files = request.FILES.getlist('files')
            if uploaded_files:
                bot.uploaded_file_data = "\n=== بيانات مؤقتة - الملفات المرفوعة ===\n"
                for f in uploaded_files:
                    file_text = load_data_professional_from_file(f, f.name)
                    bot.uploaded_file_data += f"--- ملف: {f.name} ---\n{file_text}\n"
                bot.uploaded_file_data += "=== نهاية الملفات المرفوعة ===\n"

            # 5. Generate response with history
            reply = bot.generate_response(user_message, history=history_data, user_lang=user_lang)
            
            # 6. Save message
            ChatMessage.objects.create(
                conversation=conversation,
                user=request.user,
                message=user_message,
                reply=reply
            )
            
            # Update conversion timestamp
            from django.utils import timezone
            conversation.updated_at = timezone.now()
            conversation.save()
            
            return Response({
                "reply": reply,
                "conversation_id": conversation.id,
                "conversation_title": conversation.title
            })

        except ChatConversation.DoesNotExist:
            return Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            msg = f"⚠️ حدث خطأ في النظام: {str(e)}" if user_lang == "ar" else f"⚠️ System error occurred: {str(e)}"
            return Response({"reply": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ChatConversationListView(generics.ListAPIView):
    """List all chat conversations for the current user."""
    serializer_class = ChatConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatConversation.objects.filter(user=self.request.user).order_by('-updated_at')

class ChatConversationDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete a single conversation (includes messages)."""
    serializer_class = ChatConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatConversation.objects.filter(user=self.request.user)

class ChatMessageListView(generics.ListAPIView):
    """Historical catch-all view for messages."""
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatMessage.objects.filter(user=self.request.user).order_by('-timestamp')

# ─────────────────────────────────────────────
# PASSWORD RESET VIEWS
# ─────────────────────────────────────────────

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings

class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from django.core.mail import EmailMultiAlternatives
        email = request.data.get('email')
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            frontend_url = request.data.get('frontend_url', '').rstrip('/')
            if not frontend_url:
                frontend_url = 'http://127.0.0.1:5500/index.html'
            reset_url = f"{frontend_url}?uid={uid}&token={token}"
            
            subject = "Reset Your StockPad Password"
            plain_message = f"Hello,\n\nClick this link to reset your password:\n{reset_url}\n\nIf you didn't request this, ignore this email."
            html_message = f"""
<div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 30px; border: 1px solid #eee; border-radius: 10px;">
    <h2 style="color: #f97316;">Reset Your StockPad Password</h2>
    <p>Hello,</p>
    <p>You requested a password reset for your StockPad account.</p>
    <a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background: #f97316; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0;">
        Reset My Password
    </a>
    <p style="color: #999; font-size: 12px;">If you didn't request this, please ignore this email.</p>
</div>
"""
            msg = EmailMultiAlternatives(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [email])
            msg.attach_alternative(html_message, "text/html")
            msg.send()
            
            return Response({"message": "Reset link sent if account exists."})
        except User.DoesNotExist:
            return Response({"message": "Reset link sent if account exists."})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResetPasswordConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uidb64 = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('password')
        
        if not all([uidb64, token, new_password]):
            return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            
            if default_token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response({"message": "Password reset successful."})
            else:
                return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# GOOGLE AUTHENTICATION
# ─────────────────────────────────────────────
import requests as http_requests

class GoogleAuthView(APIView):
    """
    POST /api/auth/google/
    Body: { "credential": "<Google ID token>" }
    Verifies the Google token, creates/finds the user, returns JWT tokens.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        credential = request.data.get('credential')
        if not credential:
            return Response({"error": "Google credential is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify the ID token with Google
            google_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
            google_resp = http_requests.get(google_url, timeout=10)
            if google_resp.status_code != 200:
                return Response({"error": "Invalid Google token."}, status=status.HTTP_400_BAD_REQUEST)

            google_data = google_resp.json()
            
            # Verify the token was generated for our app
            if google_data.get('aud') != settings.GOOGLE_CLIENT_ID:
                return Response({"error": "Invalid token audience. Token was not issued for this application."}, status=status.HTTP_400_BAD_REQUEST)
                
            email = google_data.get('email')
            name = google_data.get('name', '')
            picture = google_data.get('picture', '')

            if not email:
                return Response({"error": "Could not retrieve email from Google."}, status=status.HTTP_400_BAD_REQUEST)

            # Find or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email.split('@')[0],
                    'first_name': name.split(' ')[0] if name else '',
                    'last_name': ' '.join(name.split(' ')[1:]) if name else '',
                }
            )

            if created:
                # Set unusable password for Google-only users
                user.set_unusable_password()
                user.save()

            # Generate JWT tokens
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': getattr(user, 'role', 'engineer'),
                    'first_name': getattr(user, 'first_name', ''),
                    'last_name': getattr(user, 'last_name', ''),
                },
                'created': created,
            })

        except Exception as e:
            return Response({"error": f"Google authentication failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
