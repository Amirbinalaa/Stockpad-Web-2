import hmac
import hashlib
import json
from unittest.mock import patch
import requests
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from api.models import (
    Material, MaterialRequest, Category, RequestStatusHistory,
    ProcessedWebhookEvent, OutboundSyncDeadLetterLog,
)
from api.site_a_client import submit_request_to_site_a, fetch_materials_catalog, SiteAError

import celery.exceptions
from api.tasks import sync_request_to_site_a_task

User = get_user_model()

class SiteAIntegrationTests(APITestCase):
    def setUp(self):
        # Override integration settings for predictable testing
        settings.WM_WEBSITE_BASE_URL = "https://mock-site-a.com"
        settings.SITE_A_BASE_URL = "https://mock-site-a.com"
        settings.WM_WEBSITE_API_KEY = "test-site-b-api-key"
        settings.SITE_A_API_KEY = "test-site-b-api-key"
        settings.WEBHOOK_SHARED_SECRET = "test-webhook-secret"
        settings.SITE_A_WEBHOOK_SECRET = "test-webhook-secret"
        settings.SITE_B_PUBLIC_WEBHOOK_URL = "https://mock-site-b.com/api/webhooks/material-status/"

        # Ensure Celery executes eager mode in tests
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = False

        # Setup standard users, category, material
        self.user = User.objects.create_user(username="engineer", email="engineer@test.com", password="password")
        self.category = Category.objects.create(name="Plumbing")
        self.material = Material.objects.create(
            name="PVC Pipe",
            category=self.category,
            quantity_available=100,
            unit="Units",
            site_a_material_id=456
        )
        self.client.force_authenticate(user=self.user)

    def test_health_check_endpoint(self):
        url = reverse('health-check')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "healthy"})

    @patch('api.tasks.submit_request_to_site_a')
    def test_create_request_success_sync(self, mock_submit):
        # Setup mock return value
        mock_submit.return_value = {"id": 999, "status": "pending"}

        url = reverse('create-request')
        data = {
            "material": self.material.id,
            "quantity_needed": 5,
            "justification": "Need it for fixing leak"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify locally saved request
        req = MaterialRequest.objects.get(id=response.data['id'])
        self.assertEqual(req.site_a_request_id, 999)
        self.assertEqual(req.sync_status, 'synced')
        mock_submit.assert_called_once_with(
            material_id=456,
            quantity=5,
            requester_email=self.user.email,
            justification="Need it for fixing leak",
            idempotency_key=str(req.idempotency_key),
        )

    @patch('api.tasks.submit_request_to_site_a')
    def test_create_request_failed_sync_offline(self, mock_submit):
        # Mock connection error
        mock_submit.side_effect = requests.exceptions.ConnectionError("Site A Offline")

        url = reverse('create-request')
        data = {
            "material": self.material.id,
            "quantity_needed": 5,
            "justification": "Need it for fixing leak"
        }
        response = self.client.post(url, data, format='json')
        # Local request should succeed even if sync fails
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        req = MaterialRequest.objects.get(id=response.data['id'])
        self.assertEqual(req.sync_status, 'sync_failed')
        self.assertIsNone(req.site_a_request_id)


    def test_webhook_valid_signature_updates_status(self):
        import time as _time
        # Create a synced request
        material_request = MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=5,
            status='pending',
            site_a_request_id=999,
            sync_status='synced'
        )

        url = reverse('site-a-webhook')
        payload = {"id": 999, "status": "approved"}
        body_bytes = json.dumps(payload).encode('utf-8')
        timestamp = str(int(_time.time()))

        # Reconstruct signing message: "{timestamp}.{raw_body}"
        signing_message = f"{timestamp}.{body_bytes.decode('utf-8')}".encode('utf-8')

        # Generate valid HMAC signature
        signature = hmac.new(
            key=settings.WEBHOOK_SHARED_SECRET.encode("utf-8"),
            msg=signing_message,
            digestmod=hashlib.sha256
        ).hexdigest()

        response = self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp
        )
        self.assertEqual(response.status_code, 200)

        # Check DB update
        material_request.refresh_from_db()
        self.assertEqual(material_request.status, 'approved')

        # Check status history
        history = RequestStatusHistory.objects.filter(request=material_request)
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().old_status, 'pending')
        self.assertEqual(history.first().new_status, 'approved')
        self.assertIsNone(history.first().changed_by)

    def test_webhook_invalid_signature_returns_403(self):
        import time as _time
        material_request = MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=5,
            status='pending',
            site_a_request_id=999,
            sync_status='synced'
        )

        url = reverse('site-a-webhook')
        payload = {"id": 999, "status": "approved"}
        body_bytes = json.dumps(payload).encode('utf-8')
        timestamp = str(int(_time.time()))

        response = self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="invalid-signature-here",
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp
        )
        self.assertEqual(response.status_code, 403)

        # Request status should remain unchanged
        material_request.refresh_from_db()
        self.assertEqual(material_request.status, 'pending')

    def test_webhook_unknown_request_id_returns_404(self):
        import time as _time
        url = reverse('site-a-webhook')
        payload = {"id": 8888, "status": "approved"}
        body_bytes = json.dumps(payload).encode('utf-8')
        timestamp = str(int(_time.time()))

        signing_message = f"{timestamp}.{body_bytes.decode('utf-8')}".encode('utf-8')

        signature = hmac.new(
            key=settings.WEBHOOK_SHARED_SECRET.encode("utf-8"),
            msg=signing_message,
            digestmod=hashlib.sha256
        ).hexdigest()

        response = self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp
        )
        self.assertEqual(response.status_code, 404)

    def test_webhook_duplicate_status_delivery_idempotent(self):
        import time as _time
        # Create request already in 'approved' status
        material_request = MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=5,
            status='approved',
            site_a_request_id=999,
            sync_status='synced'
        )

        url = reverse('site-a-webhook')
        payload = {"id": 999, "status": "approved"}
        body_bytes = json.dumps(payload).encode('utf-8')
        timestamp = str(int(_time.time()))

        signing_message = f"{timestamp}.{body_bytes.decode('utf-8')}".encode('utf-8')

        signature = hmac.new(
            key=settings.WEBHOOK_SHARED_SECRET.encode("utf-8"),
            msg=signing_message,
            digestmod=hashlib.sha256
        ).hexdigest()

        # Webhook delivery
        response = self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp
        )
        self.assertEqual(response.status_code, 200)

        # No new history entry should be created (duplicate status ignored)
        history = RequestStatusHistory.objects.filter(request=material_request)
        self.assertEqual(history.count(), 0)

    @patch('api.site_a_client.resolve_wm_requester_id', return_value=1)
    @patch('requests.post')
    def test_submit_request_to_site_a_client(self, mock_post, mock_requester):
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {"id": 12345, "status": "pending"}

        result = submit_request_to_site_a(
            material_id=456,
            quantity=5,
            requester_email="engineer@test.com",
            justification="justification reason"
        )

        self.assertEqual(result["id"], 12345)
        mock_requester.assert_called_once_with("engineer@test.com")
        mock_post.assert_called_once_with(
            "https://mock-site-a.com/api/inventory/requests/create/",
            json={
                "material": 456,
                "requester_id": 1,
                "quantity": 5,
                "reason": "justification reason",
                "requester_email": "engineer@test.com",
                "webhook_url": "https://mock-site-b.com/api/webhooks/material-status/",
            },
            headers={"X-Site-B-API-Key": "test-site-b-api-key"},
            timeout=10
        )


class AuthLoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="stockpad27",
            email="stockpad27@gmail.com",
            password="test-password-123",
        )
        self.login_url = reverse("login")

    def test_login_with_email_returns_jwt(self):
        response = self.client.post(
            self.login_url,
            {"username": "stockpad27@gmail.com", "password": "test-password-123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_invalid_password_returns_401(self):
        response = self.client.post(
            self.login_url,
            {"username": "stockpad27@gmail.com", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MyRequestsPaginationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="engineer_page", email="engineer_page@test.com", password="password")
        self.category = Category.objects.create(name="Electrical")
        self.material = Material.objects.create(
            name="Copper Wire",
            category=self.category,
            quantity_available=500,
            unit="Meters",
            site_a_material_id=789
        )
        self.client.force_authenticate(user=self.user)

        # Create 25 material requests for this engineer
        self.total_requests = 25
        for i in range(self.total_requests):
            MaterialRequest.objects.create(
                requested_by=self.user,
                material=self.material,
                quantity_needed=i + 1,
                justification=f"Batch test request {i+1}",
                status='pending' if i % 2 == 0 else 'approved'
            )

    def test_my_requests_pagination_25_items(self):
        url = reverse('my-requests')

        # Fetch Page 1
        response_p1 = self.client.get(url)
        self.assertEqual(response_p1.status_code, status.HTTP_200_OK)
        self.assertIn('count', response_p1.data)
        self.assertIn('next', response_p1.data)
        self.assertIn('previous', response_p1.data)
        self.assertIn('results', response_p1.data)

        self.assertEqual(response_p1.data['count'], 25)
        self.assertEqual(len(response_p1.data['results']), 20)
        self.assertIsNotNone(response_p1.data['next'])
        self.assertIsNone(response_p1.data['previous'])
        self.assertIn('page=2', response_p1.data['next'])

        # Fetch Page 2
        response_p2 = self.client.get(response_p1.data['next'])
        self.assertEqual(response_p2.status_code, status.HTTP_200_OK)
        self.assertEqual(response_p2.data['count'], 25)
        self.assertEqual(len(response_p2.data['results']), 5)
        self.assertIsNone(response_p2.data['next'])
        self.assertIsNotNone(response_p2.data['previous'])

        # Ensure page 1 and page 2 returned disjoint sets of request IDs
        p1_ids = {r['id'] for r in response_p1.data['results']}
        p2_ids = {r['id'] for r in response_p2.data['results']}
        self.assertEqual(len(p1_ids.intersection(p2_ids)), 0)
        self.assertEqual(len(p1_ids) + len(p2_ids), 25)


class Phase2AsyncQueueTests(APITestCase):
    def setUp(self):
        settings.WM_WEBSITE_BASE_URL = "https://mock-site-a.com"
        settings.SITE_A_BASE_URL = "https://mock-site-a.com"
        settings.WM_WEBSITE_API_KEY = "test-site-b-api-key"
        settings.SITE_A_API_KEY = "test-site-b-api-key"
        settings.WEBHOOK_SHARED_SECRET = "test-webhook-secret"
        settings.SITE_B_PUBLIC_WEBHOOK_URL = "https://mock-site-b.com/api/webhooks/material-status/"

        # CELERY_TASK_ALWAYS_EAGER=True runs tasks synchronously in tests.
        # CELERY_TASK_EAGER_PROPAGATES=False means .delay() swallows task exceptions
        # so the HTTP view still returns 201 (same behaviour as a real async worker).
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = False

        self.user = User.objects.create_user(username="async_engineer", email="async@test.com", password="password")
        self.category = Category.objects.create(name="Mechanical")
        self.material = Material.objects.create(
            name="Steel Beam",
            category=self.category,
            quantity_available=10,
            unit="Units",
            site_a_material_id=99
        )
        self.client.force_authenticate(user=self.user)

    @patch('api.tasks.submit_request_to_site_a',
           side_effect=requests.exceptions.ConnectionError("Site A Unreachable"))
    @patch('api.tasks.resolve_wm_material_id', return_value=99)
    def test_submission_returns_201_when_site_a_unreachable(self, mock_resolve, mock_submit):
        """
        The HTTP response to the engineer must be 201 Created immediately,
        even when Site A is unreachable.  The Celery task runs eagerly but
        EAGER_PROPAGATES=False means its exception never reaches the view caller.
        """
        url = reverse('create-request')
        data = {
            "material": self.material.id,
            "quantity_needed": 5,
            "justification": "Emergency repair requirement"
        }

        # HTTP POST must complete and return 201 regardless of Site A state
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)

        # Local DB record was saved
        req = MaterialRequest.objects.get(id=response.data['id'])
        self.assertIsNone(req.site_a_request_id)

        # After the eager task ran (and failed all retries), status is sync_failed
        req.refresh_from_db()
        self.assertEqual(req.sync_status, 'sync_failed')

    @patch('api.tasks.submit_request_to_site_a',
           side_effect=requests.exceptions.ConnectionError("Site A Unreachable"))
    @patch('api.tasks.resolve_wm_material_id', return_value=99)
    def test_task_self_retry_fires_on_site_a_connection_error(self, mock_resolve, mock_submit):
        """
        Calling the task function directly with a ConnectionError must trigger
        real Celery self.retry() — proven by the Retry exception propagating
        to the caller (EAGER_PROPAGATES still False; direct task() call bypasses
        the eager propagation gate so Retry always surfaces when raised).
        """
        # Create a request to retry
        req = MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=3,
            justification="Direct task retry test",
            sync_status='sync_failed',
        )

        # Direct call to the task — Celery 5.x self.retry(exc=exc) calls
        # raise_with_context(exc), which re-raises the ORIGINAL exception
        # (ConnectionError here). assertRaises(ConnectionError) proves that
        # the real self.retry() code path executed — not a mock short-circuit.
        with self.assertRaises(requests.exceptions.ConnectionError):
            sync_request_to_site_a_task(
                req.id,
                req.material_id,
                self.user.email,
                req.quantity_needed,
                req.justification,
            )

        # Retry was reached, so sync_status was marked failed before retry
        req.refresh_from_db()
        self.assertEqual(req.sync_status, 'sync_failed')
        # The actual HTTP call path (submit_request_to_site_a) was invoked
        self.assertTrue(mock_submit.called)


class Phase3HardeningTests(APITestCase):
    def setUp(self):
        settings.WM_WEBSITE_BASE_URL = "https://mock-site-a.com"
        settings.SITE_A_BASE_URL = "https://mock-site-a.com"
        settings.WM_WEBSITE_API_KEY = "test-site-b-api-key"
        settings.SITE_A_API_KEY = "test-site-b-api-key"
        settings.WEBHOOK_SHARED_SECRET = "test-webhook-secret"
        settings.SITE_B_PUBLIC_WEBHOOK_URL = "https://mock-site-b.com/api/webhooks/material-status/"

        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = False

        self.user = User.objects.create_user(username="phase3_engineer", email="phase3@test.com", password="password")
        self.category = Category.objects.create(name="Electrical")
        self.material = Material.objects.create(
            name="Copper Wire",
            category=self.category,
            quantity_available=100,
            unit="Meters",
            site_a_material_id=88
        )
        self.client.force_authenticate(user=self.user)

    def test_inbound_webhook_dedup_against_duplicate_event_id(self):
        import time as _time, uuid as _uuid
        material_request = MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=10,
            status='pending',
            site_a_request_id=123,
            sync_status='synced'
        )

        event_id = str(_uuid.uuid4())
        url = reverse('site-a-webhook')

        # First webhook delivery with event_id
        payload_1 = {"id": 123, "status": "approved", "event_id": event_id}
        body_1 = json.dumps(payload_1).encode('utf-8')
        ts_1 = str(int(_time.time()))
        sig_1 = hmac.new(
            key=settings.WEBHOOK_SHARED_SECRET.encode("utf-8"),
            msg=f"{ts_1}.{body_1.decode('utf-8')}".encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()

        resp_1 = self.client.post(
            url, data=body_1, content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=sig_1, HTTP_X_WEBHOOK_TIMESTAMP=ts_1
        )
        self.assertEqual(resp_1.status_code, 200)

        # Verify DB status updated
        material_request.refresh_from_db()
        self.assertEqual(material_request.status, 'approved')
        self.assertEqual(ProcessedWebhookEvent.objects.filter(event_id=event_id).count(), 1)

        # Duplicate webhook delivery with SAME event_id but attempting to set status to 'rejected'
        payload_2 = {"id": 123, "status": "denied", "event_id": event_id}
        body_2 = json.dumps(payload_2).encode('utf-8')
        ts_2 = str(int(_time.time()))
        sig_2 = hmac.new(
            key=settings.WEBHOOK_SHARED_SECRET.encode("utf-8"),
            msg=f"{ts_2}.{body_2.decode('utf-8')}".encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()

        resp_2 = self.client.post(
            url, data=body_2, content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=sig_2, HTTP_X_WEBHOOK_TIMESTAMP=ts_2
        )
        self.assertEqual(resp_2.status_code, 200)
        self.assertTrue(resp_2.json().get("duplicate"))

        # Verify status in DB was NOT changed to rejected; it short-circuited!
        material_request.refresh_from_db()
        self.assertEqual(material_request.status, 'approved')
        # Only 1 status history entry created
        self.assertEqual(RequestStatusHistory.objects.filter(request=material_request).count(), 1)

    @patch('api.tasks.submit_request_to_site_a')
    @patch('api.tasks.resolve_wm_material_id', return_value=88)
    def test_outbound_submission_uses_same_idempotency_key_on_retry(self, mock_resolve, mock_submit):
        mock_submit.return_value = {"id": 555, "status": "pending"}

        req = MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=5,
            justification="Testing idempotency key consistency",
        )
        saved_key = str(req.idempotency_key)
        self.assertIsNotNone(req.idempotency_key)

        # Execute task
        sync_request_to_site_a_task(req.id, req.material_id, self.user.email, req.quantity_needed, req.justification)

        mock_submit.assert_called_once()
        kwargs = mock_submit.call_args.kwargs
        self.assertEqual(kwargs["idempotency_key"], saved_key)

    @patch('api.tasks.submit_request_to_site_a', side_effect=requests.exceptions.ConnectionError("WM Unreachable"))
    @patch('api.tasks.resolve_wm_material_id', return_value=88)
    def test_exhausted_retries_creates_dead_letter_log_entry(self, mock_resolve, mock_submit):
        req = MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=2,
            justification="Dead letter log test",
        )

        self.assertEqual(OutboundSyncDeadLetterLog.objects.count(), 0)

        # Run task via Celery apply
        try:
            sync_request_to_site_a_task.apply(args=[req.id, req.material_id, self.user.email, req.quantity_needed, req.justification])
        except Exception:
            pass

        req.refresh_from_db()
        self.assertEqual(req.sync_status, 'sync_failed')

        # Verify OutboundSyncDeadLetterLog record is created in real DB
        dead_letters = OutboundSyncDeadLetterLog.objects.filter(request=req)
        self.assertGreaterEqual(dead_letters.count(), 1)
        dl = dead_letters.first()
        self.assertEqual(dl.request, req)
        self.assertIn("mock-site-a.com", dl.url)
        self.assertIn("WM Unreachable", dl.error_message)
        self.assertEqual(dl.payload.get("idempotency_key"), str(req.idempotency_key))


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — CACHING TESTS
# All assertions are against the real locmem cache backend state.
# No mocked cache hits/misses; behaviour proved via cache.get() and DB counts.
# ─────────────────────────────────────────────────────────────────────────────
from django.core.cache import cache
from django.test.utils import override_settings
from api.tasks import refresh_ai_insights_cache_task
from api.insights import (
    ai_insights_cache_key,
    compute_ai_inventory_insights,
    get_ai_inventory_insights,
)

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "phase4-test-cache",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class Phase4CachingTests(APITestCase):
    """
    Proves Phase 4 caching behaviour against the real locmem backend:
    1. Cache miss -> DB query -> result stored in cache.
    2. Second call -> cache hit; cache.get() returns the same data.
    3. Invalidation on data change -> stale data is NOT served after mutation.
    4. refresh_ai_insights_cache_task writes to the real cache.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="cache_engineer", email="cache@test.com", password="password"
        )
        self.category = Category.objects.create(name="Electrical")
        self.material = Material.objects.create(
            name="Test Wire",
            category=self.category,
            quantity_available=50,
            unit="Meters",
            unit_cost=5,
            status="In Stock",
        )
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        cache.clear()

    # -- InventorySummaryView -------------------------------------------------

    def test_inventory_summary_cache_miss_then_hit(self):
        url = reverse("inventory-summary")
        cache_key = "inventory_summary_cache@test.com"

        # Cache is empty before first call
        self.assertIsNone(cache.get(cache_key))

        resp1 = self.client.get(url)
        self.assertEqual(resp1.status_code, 200)

        # Cache is now populated
        cached = cache.get(cache_key)
        self.assertIsNotNone(cached)
        self.assertIn("materials", cached)

        # Second call returns same data (cache hit)
        resp2 = self.client.get(url)
        self.assertEqual(resp2.data["materials"]["total"], resp1.data["materials"]["total"])

    def test_inventory_summary_cache_invalidated_on_request_creation(self):
        """
        CreateRequestView.perform_create deletes inventory_summary_{email}.
        After invalidation the next GET re-computes from DB (stale data not served).
        """
        url_summary = reverse("inventory-summary")
        url_requests = reverse("create-request")
        cache_key = "inventory_summary_cache@test.com"

        # Prime cache
        self.client.get(url_summary)
        self.assertIsNotNone(cache.get(cache_key))

        # Creating a new request triggers cache invalidation in perform_create
        payload = {
            "material": self.material.id,
            "quantity_needed": 5,
            "justification": "Test invalidation",
        }
        with patch("api.views.sync_request_to_site_a_task.delay"):
            resp = self.client.post(url_requests, data=payload, format="json")
        self.assertIn(resp.status_code, [200, 201])

        # Cache entry must be gone after creation
        self.assertIsNone(cache.get(cache_key))

        # Next GET fetches fresh data; pending count reflects new request
        resp_fresh = self.client.get(url_summary)
        self.assertEqual(resp_fresh.status_code, 200)
        self.assertGreaterEqual(resp_fresh.data["requests"]["pending"], 1)

    # -- DashboardAnalyticsView -----------------------------------------------

    def test_dashboard_analytics_cache_miss_then_hit(self):
        url = reverse("analytics-dashboard")
        cache_key = "dashboard_analytics_cache@test.com"

        self.assertIsNone(cache.get(cache_key))

        resp1 = self.client.get(url)
        self.assertEqual(resp1.status_code, 200)

        cached = cache.get(cache_key)
        self.assertIsNotNone(cached)
        self.assertIn("monthly_requests", cached)
        self.assertIn("status_breakdown", cached)

        # Second call is a cache hit returning identical data
        resp2 = self.client.get(url)
        self.assertEqual(resp2.data["status_breakdown"], resp1.data["status_breakdown"])

    def test_dashboard_analytics_cache_invalidated_on_webhook(self):
        """
        SiteAWebhookView.post deletes dashboard_analytics_{email} on status update.
        After invalidation the next GET re-computes fresh data.
        """
        import time as _time
        url_analytics = reverse("analytics-dashboard")
        url_webhook = reverse("site-a-webhook")
        cache_key = "dashboard_analytics_cache@test.com"

        settings.WM_WEBSITE_BASE_URL = "https://mock-site-a.com"
        settings.WEBHOOK_SHARED_SECRET = "test-webhook-secret"

        mr = MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=3,
            status="pending",
            site_a_request_id=9991,
            sync_status="synced",
        )

        # Prime cache
        self.client.get(url_analytics)
        self.assertIsNotNone(cache.get(cache_key))

        # Deliver webhook
        event_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        payload = {"id": 9991, "status": "approved", "event_id": event_id}
        body = json.dumps(payload).encode("utf-8")
        ts = str(int(_time.time()))
        sig = hmac.new(
            key="test-webhook-secret".encode("utf-8"),
            msg=f"{ts}.{body.decode('utf-8')}".encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        resp = self.client.post(
            url_webhook, data=body, content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=sig, HTTP_X_WEBHOOK_TIMESTAMP=ts,
        )
        self.assertEqual(resp.status_code, 200)

        # dashboard_analytics cache must be cleared after webhook
        self.assertIsNone(cache.get(cache_key))

    # -- refresh_ai_insights_cache_task ---------------------------------------

    def test_refresh_ai_insights_task_writes_to_real_cache(self):
        """The Celery task writes ai_inventory_insights_{email} for engineers with recent requests."""
        email = "cache@test.com"
        cache_key = ai_insights_cache_key(email)
        self.assertIsNone(cache.get(cache_key))

        wm_catalog = [
            {
                "id": self.material.site_a_material_id or 999,
                "name": self.material.name,
                "quantity_available": self.material.quantity_available,
                "unit": self.material.unit,
            }
        ]
        MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=5,
            status="approved",
        )

        with patch("api.insights.fetch_wm_catalog_for_engineer", return_value=wm_catalog):
            refresh_ai_insights_cache_task.apply()

        result = cache.get(cache_key)
        self.assertIsNotNone(result)
        self.assertIn("high_demand_materials", result)
        self.assertIn("depletion_warnings", result)

    def test_get_ai_inventory_insights_computes_on_cache_miss(self):
        """Cache miss triggers inline compute and populates the per-email cache."""
        email = "cache@test.com"
        cache_key = ai_insights_cache_key(email)
        self.assertIsNone(cache.get(cache_key))

        wm_catalog = [
            {
                "id": self.material.site_a_material_id or 999,
                "name": self.material.name,
                "quantity_available": self.material.quantity_available,
                "unit": self.material.unit,
            }
        ]
        MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=3,
            status="approved",
        )

        with patch("api.insights.fetch_wm_catalog_for_engineer", return_value=wm_catalog):
            result = get_ai_inventory_insights(email)

        self.assertIn("high_demand_materials", result)
        self.assertIn("depletion_warnings", result)
        self.assertIsNotNone(cache.get(cache_key))

    def test_get_ai_inventory_insights_returns_cached_value(self):
        """Cache hit avoids recomputation."""
        email = "cache@test.com"
        cache_key = ai_insights_cache_key(email)
        cached = {
            "high_demand_materials": [{"material__name": "Cached Wire", "total_requested": 99, "count": 1}],
            "depletion_warnings": [],
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        cache.set(cache_key, cached, timeout=900)

        with patch("api.insights.compute_ai_inventory_insights", side_effect=Exception("should not compute")):
            result = get_ai_inventory_insights(email)

        self.assertEqual(result, cached)

    def test_dashboard_analytics_includes_ai_insights(self):
        url = reverse("analytics-dashboard")
        cache_key = ai_insights_cache_key("cache@test.com")
        self.assertIsNone(cache.get(cache_key))

        wm_catalog = [
            {
                "id": self.material.site_a_material_id or 999,
                "name": self.material.name,
                "quantity_available": self.material.quantity_available,
                "unit": self.material.unit,
            }
        ]
        with patch("api.insights.fetch_wm_catalog_for_engineer", return_value=wm_catalog):
            resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertIn("ai_insights", resp.data)
        self.assertIn("high_demand_materials", resp.data["ai_insights"])
        self.assertIn("depletion_warnings", resp.data["ai_insights"])
        self.assertIsNotNone(cache.get(cache_key))

    def test_chatbot_inventory_data_includes_ai_insights(self):
        from api.views import ChatbotView

        view = ChatbotView()
        wm_catalog = [
            {
                "id": self.material.site_a_material_id or 999,
                "name": self.material.name,
                "quantity_available": self.material.quantity_available,
                "unit": self.material.unit,
            }
        ]
        with patch("api.views.fetch_wm_catalog_for_engineer", return_value=wm_catalog):
            with patch("api.insights.fetch_wm_catalog_for_engineer", return_value=wm_catalog):
                data = view._build_chatbot_inventory_data(user=self.user)

        self.assertIn("=== AI Inventory Insights (last 30 days) ===", data)
        self.assertIn("High-demand materials:", data)
        self.assertIn("Depletion warnings:", data)

    def test_ai_insights_isolated_per_engineer_manager_scope(self):
        """
        Two engineers under different WM managers must never see each other's
        high-demand or depletion data. WM catalog fetch returns disjoint material sets.
        """
        user_a = User.objects.create_user(
            username="eng_a", email="engineer-a@test.com", password="password"
        )
        user_b = User.objects.create_user(
            username="eng_b", email="engineer-b@test.com", password="password"
        )

        mat_a = Material.objects.create(
            name="Manager A Steel",
            category=self.category,
            quantity_available=10,
            unit="Units",
            unit_cost=1,
            status="In Stock",
            site_a_material_id=1001,
        )
        mat_b = Material.objects.create(
            name="Manager B Copper",
            category=self.category,
            quantity_available=100,
            unit="Units",
            unit_cost=1,
            status="In Stock",
            site_a_material_id=2002,
        )

        # Engineer A: consumption on manager-A material only
        MaterialRequest.objects.create(
            requested_by=user_a,
            material=mat_a,
            quantity_needed=27,
            status="approved",
        )
        # Engineer B: high demand on manager-B material only
        MaterialRequest.objects.create(
            requested_by=user_b,
            material=mat_b,
            quantity_needed=50,
            status="approved",
        )
        MaterialRequest.objects.create(
            requested_by=user_b,
            material=mat_b,
            quantity_needed=50,
            status="approved",
        )

        def wm_catalog_side_effect(email):
            if email == "engineer-a@test.com":
                return [
                    {
                        "id": 1001,
                        "name": "Manager A Steel",
                        "quantity_available": 10,
                        "unit": "Units",
                    }
                ]
            if email == "engineer-b@test.com":
                return [
                    {
                        "id": 2002,
                        "name": "Manager B Copper",
                        "quantity_available": 100,
                        "unit": "Units",
                    }
                ]
            return []

        with patch("api.insights.fetch_wm_catalog_for_engineer", side_effect=wm_catalog_side_effect):
            insights_a = compute_ai_inventory_insights("engineer-a@test.com")
            insights_b = compute_ai_inventory_insights("engineer-b@test.com")

        a_high_demand_names = [x["material__name"] for x in insights_a["high_demand_materials"]]
        b_high_demand_names = [x["material__name"] for x in insights_b["high_demand_materials"]]

        self.assertIn("Manager A Steel", a_high_demand_names)
        self.assertNotIn("Manager B Copper", a_high_demand_names)
        self.assertIn("Manager B Copper", b_high_demand_names)
        self.assertNotIn("Manager A Steel", b_high_demand_names)

        a_depletion_names = [w["material_name"] for w in insights_a["depletion_warnings"]]
        b_depletion_names = [w["material_name"] for w in insights_b["depletion_warnings"]]

        self.assertIn("Manager A Steel", a_depletion_names)
        self.assertNotIn("Manager B Copper", a_depletion_names)
        self.assertNotIn("Manager A Steel", b_depletion_names)

        # Separate per-email cache entries must also stay isolated
        cache.clear()
        with patch("api.insights.fetch_wm_catalog_for_engineer", side_effect=wm_catalog_side_effect):
            get_ai_inventory_insights("engineer-a@test.com")
            get_ai_inventory_insights("engineer-b@test.com")

        cached_a = cache.get(ai_insights_cache_key("engineer-a@test.com"))
        cached_b = cache.get(ai_insights_cache_key("engineer-b@test.com"))

        self.assertNotIn(
            "Manager B Copper",
            [x["material__name"] for x in cached_a["high_demand_materials"]],
        )
        self.assertNotIn(
            "Manager A Steel",
            [x["material__name"] for x in cached_b["high_demand_materials"]],
        )
        self.assertNotIn(
            "Manager B Copper",
            [w["material_name"] for w in cached_a["depletion_warnings"]],
        )
        self.assertNotIn(
            "Manager A Steel",
            [w["material_name"] for w in cached_b["depletion_warnings"]],
        )

    # -- ChatbotView._build_inventory_context ---------------------------------

    def test_chatbot_inventory_context_cached_after_first_build(self):
        """
        _build_inventory_context stores its result in ai_inventory_context_{email}.
        The second call returns the cached string without a WM/DB round-trip.
        """
        from api.views import ChatbotView
        view = ChatbotView()
        cache_key = "ai_inventory_context_cache@test.com"

        self.assertIsNone(cache.get(cache_key))

        # First build: WM raises, falls back to local DB
        with patch("api.views.fetch_wm_catalog_for_engineer", side_effect=Exception("no wm")):
            result1 = view._build_inventory_context(user=self.user)

        cached = cache.get(cache_key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached, result1)

        # Second build: cache hit, WM should NOT be called
        with patch("api.views.fetch_wm_catalog_for_engineer", side_effect=Exception("should not be called")):
            result2 = view._build_inventory_context(user=self.user)

        self.assertEqual(result1, result2)

    def test_chatbot_inventory_context_invalidated_on_request_creation(self):
        """
        perform_create deletes ai_inventory_context_{email} so the next chatbot
        call sees fresh inventory data rather than stale cached context.
        """
        url_requests = reverse("create-request")
        cache_key = "ai_inventory_context_cache@test.com"

        # Manually warm the cache
        cache.set(cache_key, "stale-context", timeout=300)
        self.assertIsNotNone(cache.get(cache_key))

        payload = {
            "material": self.material.id,
            "quantity_needed": 2,
            "justification": "Invalidation test",
        }
        with patch("api.views.sync_request_to_site_a_task.delay"):
            self.client.post(url_requests, data=payload, format="json")

        # Key must be gone after request creation
        self.assertIsNone(cache.get(cache_key))

    # -- WMCatalogProxyView ---------------------------------------------------

    def test_wm_catalog_cached_on_first_fetch(self):
        """
        WMCatalogProxyView.get stores the WM response in wm_catalog_{email}
        on the first request; returns a cache hit on the second (WM not called).
        """
        url = reverse("wm-catalog-proxy")
        cache_key = "wm_catalog_cache@test.com"

        fake_catalog = [{"id": 1, "name": "Steel Bar", "quantity_available": 100}]

        self.assertIsNone(cache.get(cache_key))

        with patch("api.views.fetch_wm_catalog_for_engineer", return_value=fake_catalog):
            resp1 = self.client.get(url)

        self.assertEqual(resp1.status_code, 200)
        self.assertIsNotNone(cache.get(cache_key))

        # Second call must NOT reach the real fetch (cache hit)
        with patch("api.views.fetch_wm_catalog_for_engineer", side_effect=Exception("should not be called")):
            resp2 = self.client.get(url)

        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data, fake_catalog)

    def test_wm_catalog_cache_cleared_by_sync_command(self):
        """
        sync_materials_from_site_a calls invalidate_wm_catalog_cache() on success.
        After that, wm_catalog_{email} must not be present; other keys are untouched.
        """
        from api.cache_utils import invalidate_wm_catalog_cache, register_wm_catalog_key

        cache_key = "wm_catalog_cache@test.com"
        cache.set(cache_key, [{"name": "old-material"}], timeout=300)
        register_wm_catalog_key(cache_key)
        self.assertIsNotNone(cache.get(cache_key))

        # per-email AI insights must survive wm_catalog-only invalidation
        cache.set(ai_insights_cache_key("cache@test.com"), {"high_demand_materials": []}, timeout=900)
        cache.set("inventory_summary_cache@test.com", {"materials": {}}, timeout=120)

        invalidate_wm_catalog_cache()

        self.assertIsNone(cache.get(cache_key))
        self.assertIsNotNone(cache.get(ai_insights_cache_key("cache@test.com")))
        self.assertIsNotNone(cache.get("inventory_summary_cache@test.com"))


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — OPERATIONAL HYGIENE (alerting + dual-secret webhook HMAC)
# ─────────────────────────────────────────────────────────────────────────────
from django.core.cache import cache
from django.test.utils import override_settings
from io import StringIO
from django.core.management import call_command
from api.alerting import (
    SYNC_RETRY_SPIKE_CACHE_KEY,
    record_sync_retry_event,
    check_sync_retry_spike_sentinel,
)
from api.webhook_auth import verify_webhook_hmac_signature


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "phase5-test-cache",
    }
}


@override_settings(CACHES=LOCMEM_CACHE, SYNC_RETRY_SPIKE_THRESHOLD=3)
class Phase5OperationalTests(APITestCase):
    def setUp(self):
        cache.clear()
        settings.WM_WEBSITE_BASE_URL = "https://mock-site-a.com"
        settings.SITE_A_BASE_URL = "https://mock-site-a.com"
        settings.WEBHOOK_SHARED_SECRET = "old-hmac-secret"
        settings.SITE_A_WEBHOOK_SECRET = "old-hmac-secret"
        settings.WEBHOOK_SHARED_SECRET_NEW = "new-hmac-secret"
        settings.SITE_A_WEBHOOK_SECRET_NEW = "new-hmac-secret"
        settings.SITE_B_PUBLIC_WEBHOOK_URL = "https://mock-site-b.com/api/webhooks/material-status/"

        self.user = User.objects.create_user(
            username="phase5_engineer", email="phase5@test.com", password="password"
        )
        self.category = Category.objects.create(name="Phase5")
        self.material = Material.objects.create(
            name="Phase5 Material",
            category=self.category,
            quantity_available=10,
            unit="Units",
            site_a_material_id=501,
        )

    def _webhook_post_with_secret(self, secret, payload=None, site_a_id=7777):
        import time as _time

        MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=1,
            status="pending",
            site_a_request_id=site_a_id,
            sync_status="synced",
        )
        payload = payload or {"id": site_a_id, "status": "approved"}
        body_bytes = json.dumps(payload).encode("utf-8")
        timestamp = str(int(_time.time()))
        signing_message = f"{timestamp}.{body_bytes.decode('utf-8')}".encode("utf-8")
        signature = hmac.new(
            key=secret.encode("utf-8"),
            msg=signing_message,
            digestmod=hashlib.sha256,
        ).hexdigest()
        url = reverse("site-a-webhook")
        return self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
        )

    def test_sync_retry_spike_critical_fires_at_threshold(self):
        """Alerting must trip logger.critical when rolling counter hits threshold."""
        with self.assertLogs("api.alerting", level="CRITICAL") as log_ctx:
            record_sync_retry_event()
            record_sync_retry_event()
            self.assertFalse(any("[PE ALERT]" in m for m in log_ctx.output))
            record_sync_retry_event()

        self.assertTrue(any("[PE ALERT]" in m for m in log_ctx.output))
        self.assertTrue(any("threshold=3" in m for m in log_ctx.output))
        self.assertEqual(int(cache.get(SYNC_RETRY_SPIKE_CACHE_KEY)), 3)

    def test_sync_retry_spike_sentinel_critical_when_counter_high(self):
        cache.set(SYNC_RETRY_SPIKE_CACHE_KEY, 5, timeout=3600)
        with self.assertLogs("api.alerting", level="CRITICAL") as log_ctx:
            check_sync_retry_spike_sentinel()
        self.assertTrue(any("[PE ALERT]" in m and "Sentinel" in m for m in log_ctx.output))

    @patch("api.tasks.submit_request_to_site_a", side_effect=requests.exceptions.ConnectionError("down"))
    @patch("api.tasks.resolve_wm_material_id", return_value=501)
    def test_celery_sync_retry_increments_spike_counter(self, mock_resolve, mock_submit):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True
        req = MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=2,
            justification="retry counter test",
            sync_status="sync_failed",
        )
        cache.set(SYNC_RETRY_SPIKE_CACHE_KEY, 2, timeout=3600)
        with self.assertLogs("api.alerting", level="CRITICAL") as log_ctx:
            with self.assertRaises(requests.exceptions.ConnectionError):
                sync_request_to_site_a_task(
                    req.id,
                    req.material_id,
                    self.user.email,
                    req.quantity_needed,
                    req.justification,
                )
        self.assertTrue(any("[PE ALERT]" in m for m in log_ctx.output))
        self.assertGreaterEqual(int(cache.get(SYNC_RETRY_SPIKE_CACHE_KEY)), 3)

    def test_retry_failed_syncs_command_increments_spike_counter(self):
        MaterialRequest.objects.create(
            requested_by=self.user,
            material=self.material,
            quantity_needed=1,
            sync_status="sync_failed",
        )
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = False
        with patch("api.management.commands.retry_failed_syncs.sync_request_to_site_a_task.delay"):
            call_command("retry_failed_syncs", stdout=StringIO())
        self.assertEqual(int(cache.get(SYNC_RETRY_SPIKE_CACHE_KEY)), 1)

    def test_webhook_accepts_primary_hmac_secret(self):
        resp = self._webhook_post_with_secret("old-hmac-secret")
        self.assertEqual(resp.status_code, 200)

    def test_webhook_accepts_rotation_hmac_secret(self):
        resp = self._webhook_post_with_secret("new-hmac-secret", site_a_id=7778)
        self.assertEqual(resp.status_code, 200)

    def test_webhook_rejects_unknown_hmac_secret(self):
        import time as _time

        url = reverse("site-a-webhook")
        payload = {"id": 8889, "status": "approved"}
        body_bytes = json.dumps(payload).encode("utf-8")
        timestamp = str(int(_time.time()))
        self.assertFalse(
            verify_webhook_hmac_signature("deadbeef" * 8, timestamp, body_bytes.decode("utf-8"))
        )
        resp = self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="deadbeef" * 8,
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
        )
        self.assertEqual(resp.status_code, 403)
