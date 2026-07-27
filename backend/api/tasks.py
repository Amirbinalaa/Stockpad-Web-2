import logging
import uuid
import requests
from celery import shared_task
from django.db import connection, transaction
from django.conf import settings
from api.models import MaterialRequest, Material, OutboundSyncDeadLetterLog
from api.site_a_client import submit_request_to_site_a, resolve_wm_material_id, SiteAError
from api.alerting import record_sync_retry_event, check_sync_retry_spike_sentinel

logger = logging.getLogger('api')


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    retry_backoff=True,
)
def sync_request_to_site_a_task(self, request_id, material_pk, requester_email, quantity, reason):
    """
    Celery task: submits a material request to Site A asynchronously with automatic retries/backoff.
    """
    material_request = None
    wm_material_id = None
    try:
        material_request = MaterialRequest.objects.get(pk=request_id)

        # Fallback guard: if idempotency_key is somehow missing (e.g. legacy DB row),
        # atomically lock and persist a new UUID to the DB so retries reuse the SAME key.
        if not material_request.idempotency_key:
            with transaction.atomic():
                req_locked = MaterialRequest.objects.select_for_update().get(pk=request_id)
                if not req_locked.idempotency_key:
                    req_locked.idempotency_key = uuid.uuid4()
                    req_locked.save(update_fields=['idempotency_key'])
                material_request = req_locked

        material = Material.objects.get(pk=material_pk)
        wm_material_id = resolve_wm_material_id(material, requester_email)
        if wm_material_id is None:
            msg = (
                f"material '{material.name}' has no site_a_material_id "
                f"and WM catalog lookup failed for {requester_email}"
            )
            logger.error("[WM Request Sync Error]: %s", msg)
            MaterialRequest.objects.filter(pk=request_id).update(sync_status='sync_failed')
            OutboundSyncDeadLetterLog.objects.create(
                request=material_request,
                url=f"{settings.WM_WEBSITE_BASE_URL}/api/inventory/requests/create/",
                payload={"material_pk": material_pk, "quantity": quantity, "requester_email": requester_email},
                error_message=msg,
                attempt_count=1,
            )
            return

        if material.site_a_material_id != wm_material_id:
            Material.objects.filter(pk=material_pk).update(site_a_material_id=wm_material_id)

        site_a_response = submit_request_to_site_a(
            material_id=wm_material_id,
            quantity=quantity,
            requester_email=requester_email,
            justification=reason or "",
            idempotency_key=str(material_request.idempotency_key),
        )
        MaterialRequest.objects.filter(pk=request_id).update(
            site_a_request_id=site_a_response["id"],
            sync_status='synced',
        )
        logger.info(f"[Celery Task] Request {request_id} synced to WM Website (WM ID: {site_a_response['id']}).")
    except (SiteAError, requests.exceptions.RequestException) as exc:
        MaterialRequest.objects.filter(pk=request_id).update(sync_status='sync_failed')
        logger.error(f"[Celery Task] Failed to sync request {request_id} to WM Website: {exc}. Retrying...")
        if self.request.retries >= self.max_retries:
            payload = {
                "material": wm_material_id,
                "quantity": quantity,
                "reason": reason or "",
                "requester_email": requester_email,
                "idempotency_key": str(material_request.idempotency_key) if material_request else None,
            }
            OutboundSyncDeadLetterLog.objects.create(
                request=material_request,
                url=f"{settings.WM_WEBSITE_BASE_URL}/api/inventory/requests/create/",
                payload=payload,
                error_message=str(exc),
                attempt_count=self.request.retries + 1,
            )
        record_sync_retry_event()
        raise self.retry(exc=exc)
    finally:
        connection.close()


@shared_task
def refresh_ai_insights_cache_task():
    """
    Periodic background task: pre-computes and caches AI insights per engineer email
    for users with recent material requests.
    """
    from datetime import timedelta

    from django.utils import timezone

    from api.insights import refresh_ai_inventory_insights_cache

    try:
        thirty_days_ago = timezone.now() - timedelta(days=30)
        emails = (
            MaterialRequest.objects.filter(request_date__gte=thirty_days_ago)
            .exclude(requested_by__email="")
            .values_list("requested_by__email", flat=True)
            .distinct()
        )
        refreshed = []
        for email in emails:
            refresh_ai_inventory_insights_cache(email)
            refreshed.append(email.lower().strip())
        return refreshed
    except Exception as e:
        logger.error(f"[Celery Task] Error refreshing AI insights cache: {e}")


@shared_task
def sync_retry_spike_sentinel_task():
    """Periodic backup check for outbound sync retry spike alerting."""
    try:
        return check_sync_retry_spike_sentinel()
    except Exception as e:
        logger.error(f"[Celery Task] Error in sync retry spike sentinel: {e}")


