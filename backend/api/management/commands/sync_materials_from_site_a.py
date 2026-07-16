import logging
from django.core.management.base import BaseCommand, CommandError
from api.models import Material, Category
from api.site_a_client import fetch_materials_catalog, SiteAError
import requests

logger = logging.getLogger('api')

# Threshold: if the incoming catalog is smaller than this fraction of the
# last known local count, treat it as a suspicious/bad response and abort
# rather than silently zeroing out quantities.
DROP_THRESHOLD = 0.50


class Command(BaseCommand):
    help = "Synchronizes material stock and catalog from Website 1 (Site A)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-expected',
            type=int,
            default=0,
            dest='min_expected',
            help=(
                'Abort if the catalog response contains fewer than this many items. '
                'Useful for an initial sanity floor (e.g. --min-expected 10).'
            ),
        )

    def handle(self, *args, **options):
        min_expected = options['min_expected']

        logger.info("Starting materials catalog synchronization from Website 1.")
        self.stdout.write("Starting sync...")

        # ── Snapshot local count BEFORE fetching so we can detect a suspicious
        #    drop without touching a single row in the database yet. ──────────
        local_count_before = Material.objects.filter(
            site_a_material_id__isnull=False
        ).count()

        # ── Fetch ─────────────────────────────────────────────────────────────
        try:
            catalog = fetch_materials_catalog()
        except (SiteAError, requests.exceptions.RequestException) as e:
            msg = f"Failed to fetch materials catalog from Website 1: {e}"
            logger.error(msg)
            raise CommandError(msg)  # exits non-zero so cron/monitoring sees the failure

        if isinstance(catalog, dict):
            catalog = catalog.get("results", [])

        if not isinstance(catalog, list):
            msg = f"Invalid catalog format received from Website 1: {type(catalog)}"
            logger.error(msg)
            raise CommandError(msg)

        incoming_count = len(catalog)

        # ── Guard 1: hard floor (--min-expected) ─────────────────────────────
        if incoming_count < min_expected:
            msg = (
                f"Catalog response has only {incoming_count} item(s), "
                f"below the --min-expected floor of {min_expected}. "
                "Aborting to avoid corrupting local stock data."
            )
            logger.error(msg)
            raise CommandError(msg)

        # ── Guard 2: suspicious >50% drop against previous local count ────────
        if local_count_before > 0 and incoming_count < local_count_before * DROP_THRESHOLD:
            msg = (
                f"Catalog response contains only {incoming_count} item(s), "
                f"but the local database currently has {local_count_before} synced material(s). "
                f"This is a >{int((1 - DROP_THRESHOLD) * 100)}% drop — aborting to protect "
                "existing stock data. Investigate the Website 1 response before re-running."
            )
            logger.warning(msg)
            self.stderr.write(self.style.WARNING(msg))
            raise CommandError(msg)

        # ── Guard 3: empty response with zero local rows is OK on first run ───
        if incoming_count == 0:
            msg = (
                "Website 1 returned an empty catalog (0 items). "
                "No local materials were changed. "
                "Verify SITE_A_BASE_URL and SITE_A_API_KEY are correct."
            )
            logger.warning(msg)
            self.stderr.write(self.style.WARNING(msg))
            # Exit 0 on first run (local_count_before == 0) — not an error yet.
            # Exit non-zero if we had materials before, because something is wrong.
            if local_count_before > 0:
                raise CommandError(msg)
            return

        # ── Upsert ────────────────────────────────────────────────────────────
        synced_count = 0
        created_count = 0
        updated_count = 0

        for item in catalog:
            site_a_id = item.get("id")
            if site_a_id is None:
                continue

            category_data = item.get("category")
            if isinstance(category_data, dict):
                category_name = category_data.get("name", "Uncategorized")
            elif isinstance(category_data, str):
                category_name = category_data
            else:
                category_name = "Uncategorized"

            category, _ = Category.objects.get_or_create(name=category_name)

            qty = int(item.get("quantity_available") or item.get("quantity") or 0)
            status_val = item.get("status") or item.get("stock_status") or "In Stock"

            # Normalize status
            status_str = str(status_val).title()
            if status_str not in ['In Stock', 'Low Stock', 'Out of Stock', 'On Order']:
                if qty == 0:
                    status_str = 'Out of Stock'
                elif qty <= int(item.get("min_stock_level", 10)):
                    status_str = 'Low Stock'
                else:
                    status_str = 'In Stock'

            material, created = Material.objects.update_or_create(
                site_a_material_id=site_a_id,
                defaults={
                    "name": item.get("name", "Unnamed Material"),
                    "category": category,
                    "quantity_available": qty,
                    "unit": item.get("unit") or "Units",
                    "status": status_str,
                    "description": item.get("description", ""),
                    "unit_cost": item.get("unit_cost") or 0,
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

            action = "Created" if created else "Updated"
            logger.info(f"{action} material {material.name} (Site A ID: {site_a_id}, Stock: {qty})")
            synced_count += 1

        summary_msg = (
            f"Successfully synchronized {synced_count} materials "
            f"(Created: {created_count}, Updated: {updated_count})."
        )
        self.stdout.write(self.style.SUCCESS(summary_msg))
        logger.info(f"Materials catalog synchronization completed. {summary_msg}")
