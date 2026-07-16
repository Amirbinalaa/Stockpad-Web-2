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
from api.models import Material, MaterialRequest, Category, RequestStatusHistory
from api.site_a_client import submit_request_to_site_a, fetch_materials_catalog, SiteAError

User = get_user_model()

class SiteAIntegrationTests(APITestCase):
    def setUp(self):
        # Override integration settings for predictable testing
        settings.SITE_A_BASE_URL = "https://mock-site-a.com"
        settings.SITE_A_API_KEY = "test-site-b-api-key"
        settings.SITE_A_WEBHOOK_SECRET = "test-webhook-secret"
        settings.SITE_B_PUBLIC_WEBHOOK_URL = "https://mock-site-b.com/api/webhooks/material-status/"

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

    @patch('api.views.submit_request_to_site_a')
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
            requester_id=self.user.id,
            requester_email=self.user.email,
            quantity=5,
            reason="Need it for fixing leak"
        )

    @patch('api.views.submit_request_to_site_a')
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

        # Generate valid HMAC signature
        signature = hmac.new(
            key=settings.SITE_A_WEBHOOK_SECRET.encode("utf-8"),
            msg=body_bytes,
            digestmod=hashlib.sha256
        ).hexdigest()

        response = self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_SITE_A_SIGNATURE=signature
        )
        self.assertEqual(response.status_code, 200)

        # Check DB update
        material_request.refresh_from_db()
        self.assertEqual(material_request.status, 'approved')

        # Check status history (should have 2: 1 for creation 'pending', 1 for webhook 'approved')
        # Note: the test create here did not run signals or CreateRequestView perform_create so it has only 1 history entry from the webhook.
        history = RequestStatusHistory.objects.filter(request=material_request)
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().old_status, 'pending')
        self.assertEqual(history.first().new_status, 'approved')
        self.assertIsNone(history.first().changed_by)

    def test_webhook_invalid_signature_returns_403(self):
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

        response = self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_SITE_A_SIGNATURE="invalid-signature-here"
        )
        self.assertEqual(response.status_code, 403)

        # Request status should remain unchanged
        material_request.refresh_from_db()
        self.assertEqual(material_request.status, 'pending')

    def test_webhook_unknown_request_id_returns_404(self):
        url = reverse('site-a-webhook')
        payload = {"id": 8888, "status": "approved"}
        body_bytes = json.dumps(payload).encode('utf-8')

        signature = hmac.new(
            key=settings.SITE_A_WEBHOOK_SECRET.encode("utf-8"),
            msg=body_bytes,
            digestmod=hashlib.sha256
        ).hexdigest()

        response = self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_SITE_A_SIGNATURE=signature
        )
        self.assertEqual(response.status_code, 404)

    def test_webhook_duplicate_status_delivery_idempotent(self):
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

        signature = hmac.new(
            key=settings.SITE_A_WEBHOOK_SECRET.encode("utf-8"),
            msg=body_bytes,
            digestmod=hashlib.sha256
        ).hexdigest()

        # Webhook delivery
        response = self.client.post(
            url,
            data=body_bytes,
            content_type="application/json",
            HTTP_X_SITE_A_SIGNATURE=signature
        )
        self.assertEqual(response.status_code, 200)

        # No new history entry should be created (duplicate status ignored)
        history = RequestStatusHistory.objects.filter(request=material_request)
        self.assertEqual(history.count(), 0)

    @patch('requests.post')
    def test_submit_request_to_site_a_client(self, mock_post):
        mock_post.return_value.json.return_value = {"id": 12345, "status": "pending"}
        mock_post.return_value.raise_for_status.return_value = None

        result = submit_request_to_site_a(
            material_id=456,
            requester_id=1,
            requester_email="engineer@test.com",
            quantity=5,
            reason="justification reason"
        )

        self.assertEqual(result["id"], 12345)
        mock_post.assert_called_once_with(
            "https://mock-site-a.com/api/inventory/requests/create/",
            json={
                "material": 456,
                "requester_id": "1",
                "requester_email": "engineer@test.com",
                "quantity": "5",
                "reason": "justification reason",
                "webhook_url": "https://mock-site-b.com/api/webhooks/material-status/"
            },
            headers={"X-Site-B-API-Key": "test-site-b-api-key"},
            timeout=10
        )
