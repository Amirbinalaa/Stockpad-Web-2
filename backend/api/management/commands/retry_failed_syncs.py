import logging
from django.core.management.base import BaseCommand, CommandError
from api.models import MaterialRequest
from api.site_a_client import submit_request_to_site_a, SiteAError
import requests

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = "Retries failed material request synchronizations to Website 1 (Site A)"

    def handle(self, *args, **options):
        logger.info("Starting retry of failed material request synchronizations.")
        self.stdout.write("Checking for failed syncs...")

        failed_requests = MaterialRequest.objects.filter(sync_status='sync_failed')
        total_failed = failed_requests.count()

        if total_failed == 0:
            self.stdout.write("No failed synchronizations found.")
            logger.info("No failed request synchronizations to retry.")
            return

        self.stdout.write(f"Found {total_failed} failed requests. Retrying...")
        success_count = 0

        for req in failed_requests:
            try:
                logger.info(f"Retrying sync for request {req.id} (Material: {req.material.name}, Qty: {req.quantity_needed}).")

                if req.material.site_a_material_id is None:
                    logger.error(f"Cannot sync request {req.id}: Material {req.material.name} lacks site_a_material_id.")
                    continue

                site_a_response = submit_request_to_site_a(
                    material_id=req.material.site_a_material_id,
                    requester_id=req.requested_by.id,
                    requester_email=req.requested_by.email,
                    quantity=req.quantity_needed,
                    reason=req.justification or "",
                )

                req.site_a_request_id = site_a_response["id"]
                req.sync_status = 'synced'
                req.save(update_fields=['site_a_request_id', 'sync_status'])

                logger.info(f"Successfully retried sync for request {req.id}. Site A ID: {site_a_response['id']}.")
                success_count += 1
            except (SiteAError, requests.exceptions.RequestException) as e:
                logger.error(f"Retry failed for request {req.id}: {str(e)}")

        summary_msg = f"Finished retrying. Successfully synced {success_count} / {total_failed} requests."
        self.stdout.write(self.style.SUCCESS(summary_msg))
        logger.info(f"Completed retry of failed synchronizations. Successes: {success_count}/{total_failed}.")

        # Exit non-zero if we tried but every single retry failed — surfaces
        # the failure to cron error-mail or monitoring instead of a silent 0 exit.
        if success_count == 0 and total_failed > 0:
            raise CommandError(
                f"All {total_failed} retry attempt(s) failed. "
                "Check logs for individual errors and verify Website 1 connectivity."
            )

