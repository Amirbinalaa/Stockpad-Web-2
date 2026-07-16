from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    # Auth
    RegisterView, UserMeView, LogoutView, LoginView, ChangePasswordView,
    ForgotPasswordView, ResetPasswordConfirmView, GoogleAuthView,
    # Chatbot
    ChatbotView,
    # Inventory
    CategoryViewSet, MaterialViewSet,
    # Requests (engineer workflow)
    CreateRequestView, MyRequestsView, AllRequestsView,
    MaterialRequestDetailView,
    ChatConversationListView, ChatConversationDetailView, ChatMessageListView,
    RequestStatusHistoryViewSet,
    SiteAWebhookView,
    # Dashboard
    InventorySummaryView, DashboardAnalyticsView, NotificationsView,
    # BOM
    ProductViewSet, BOMItemViewSet,
    ProductionPlanViewSet, ProductionPlanItemViewSet, MaterialRequirementViewSet,
    # Procurement
    SupplierViewSet, ProcurementRequestViewSet, ProcurementOrderViewSet,
)

# ── Router (automatically generates list / detail / action URLs) ──────────────
router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'materials', MaterialViewSet, basename='material')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'bom-items', BOMItemViewSet, basename='bom-item')
router.register(r'production-plans', ProductionPlanViewSet, basename='production-plan')
router.register(r'production-plan-items', ProductionPlanItemViewSet, basename='production-plan-item')
router.register(r'material-requirements', MaterialRequirementViewSet, basename='material-requirement')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'procurement-requests', ProcurementRequestViewSet, basename='procurement-request')
router.register(r'procurement-orders', ProcurementOrderViewSet, basename='procurement-order')
router.register(r'request-history', RequestStatusHistoryViewSet, basename='request-history')

urlpatterns = [
    # ── Auth ─────────────────────────────────────────────────────────────────
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/me/', UserMeView.as_view(), name='me'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/password-reset/', ForgotPasswordView.as_view(), name='password-reset'),
    path('auth/password-reset-confirm/', ResetPasswordConfirmView.as_view(), name='password-reset-confirm'),
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),

    # ── Engineer request workflow (kept as explicit paths for clarity) ────────
    path('requests/', CreateRequestView.as_view(), name='create-request'),
    path('requests/mine/', MyRequestsView.as_view(), name='my-requests'),
    path('requests/all/', AllRequestsView.as_view(), name='all-requests'),
    path('webhooks/material-status/', SiteAWebhookView.as_view(), name='site-a-webhook'),
    path('requests/<int:pk>/', MaterialRequestDetailView.as_view(), name='request-detail'),

    # ── Dashboard summary ─────────────────────────────────────────────────────
    path('inventory/summary/', InventorySummaryView.as_view(), name='inventory-summary'),
    path('analytics/dashboard/', DashboardAnalyticsView.as_view(), name='analytics-dashboard'),
    path('notifications/', NotificationsView.as_view(), name='notifications'),

    # ── Chatbot ───────────────────────────────────────────────────────────────
    path('chatbot/', ChatbotView.as_view(), name='chatbot'),
    path('chatbot/conversations/', ChatConversationListView.as_view(), name='chatbot-conversations'),
    path('chatbot/conversations/<int:pk>/', ChatConversationDetailView.as_view(), name='chatbot-conversation-detail'),
    path('chatbot/history/', ChatMessageListView.as_view(), name='chatbot-history'),

    # ── Router-generated URLs (materials, categories, BOM, procurement, etc.) ─
    path('', include(router.urls)),
]
