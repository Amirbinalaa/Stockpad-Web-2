import logging
from django.core.management.base import BaseCommand
from api.models import MaterialRequest
from api.tasks import sync_request_to_site_a_task
from api.alerting import record_sync_retry_event

logger = logging.getLogger('api')


class Command(BaseCommand):
    help = "Dispatches failed material request synchronizations to Celery queue for retries/backoff"

    def handle(self, *args, **options):
        logger.info("Starting dispatch of failed material request synchronizations.")
        self.stdout.write("Checking for failed syncs...")

        failed_requests = MaterialRequest.objects.filter(sync_status='sync_failed')
        total_failed = failed_requests.count()

        if total_failed == 0:
            self.stdout.write("No failed synchronizations found.")
            logger.info("No failed request synchronizations to retry.")
            return

        self.stdout.write(f"Found {total_failed} failed requests. Dispatching to task queue...")
        for req in failed_requests:
            logger.info(f"Re-queuing sync task for request {req.id} (Material: {req.material.name}, Qty: {req.quantity_needed}).")
            record_sync_retry_event()
            sync_request_to_site_a_task.delay(
                req.id,
                req.material_id,
                req.requested_by.email,
                req.quantity_needed,
                req.justification,
            )

        summary_msg = f"Dispatched {total_failed} failed request(s) to Celery task queue."
        self.stdout.write(self.style.SUCCESS(summary_msg))
        logger.info(summary_msg)
