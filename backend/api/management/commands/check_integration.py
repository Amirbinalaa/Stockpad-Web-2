"""Sanity-check PE backend DB, auth, and WM proxy connectivity."""

import json

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection

from api.site_a_client import check_engineer_status_on_wm, fetch_wm_catalog_for_engineer


class Command(BaseCommand):
    help = "Verify database, login prerequisites, and WM site proxy connectivity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--engineer-email",
            default="stockpad27@gmail.com",
            help="Engineer email to test WM whitelist/catalog proxy against.",
        )

    def handle(self, *args, **options):
        engineer_email = options["engineer_email"].strip().lower()
        failures = 0

        self.stdout.write("StockPad PE integration check\n")

        # 1) Database
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            user_count = get_user_model().objects.count()
            self.stdout.write(self.style.SUCCESS(f"[OK] Database connected ({user_count} users)"))
        except Exception as exc:
            failures += 1
            self.stdout.write(self.style.ERROR(f"[FAIL] Database: {exc}"))

        # 2) Config alignment
        self.stdout.write(f"  PE backend URL: {settings.PE_BACKEND_PUBLIC_URL}")
        self.stdout.write(f"  WM base URL:    {settings.WM_WEBSITE_BASE_URL}")
        self.stdout.write(f"  Webhook URL:    {settings.SITE_B_PUBLIC_WEBHOOK_URL}")

        if settings.WM_WEBSITE_BASE_URL.rstrip("/") != "https://stockpad-backend-production.up.railway.app":
            failures += 1
            self.stdout.write(self.style.WARNING("[WARN] WM_WEBSITE_BASE_URL is not the production WM domain."))

        if not settings.WM_WEBSITE_API_KEY:
            failures += 1
            self.stdout.write(self.style.ERROR("[FAIL] WM_WEBSITE_API_KEY is missing."))
        else:
            self.stdout.write(self.style.SUCCESS("[OK] WM_WEBSITE_API_KEY is set"))

        # 3) WM engineer status
        status = check_engineer_status_on_wm(engineer_email)
        if status.get("connected"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"[OK] WM engineer status for {engineer_email}: connected "
                    f"(manager={status.get('manager_name')})"
                )
            )
        else:
            failures += 1
            self.stdout.write(
                self.style.WARNING(
                    f"[WARN] WM engineer status for {engineer_email}: not connected "
                    f"({json.dumps(status)})"
                )
            )

        # 4) WM catalog proxy
        try:
            materials = fetch_wm_catalog_for_engineer(engineer_email)
            count = len(materials) if isinstance(materials, list) else 0
            self.stdout.write(self.style.SUCCESS(f"[OK] WM catalog proxy returned {count} materials"))
        except Exception as exc:
            failures += 1
            self.stdout.write(self.style.ERROR(f"[FAIL] WM catalog proxy: {exc}"))

        # 5) PE login endpoint smoke test (invalid creds should be 401, not 500)
        login_url = f"{settings.PE_BACKEND_PUBLIC_URL}/api/auth/login/"
        try:
            resp = requests.post(
                login_url,
                json={"username": "integration-check@invalid.local", "password": "wrong"},
                timeout=15,
            )
            if resp.status_code == 500:
                failures += 1
                self.stdout.write(self.style.ERROR(f"[FAIL] Login endpoint returned 500: {resp.text[:300]}"))
            elif resp.status_code in (401, 400):
                self.stdout.write(self.style.SUCCESS(f"[OK] Login endpoint reachable (HTTP {resp.status_code})"))
            else:
                self.stdout.write(self.style.WARNING(f"[WARN] Login endpoint HTTP {resp.status_code}"))
        except requests.exceptions.RequestException as exc:
            failures += 1
            self.stdout.write(self.style.ERROR(f"[FAIL] Login endpoint unreachable: {exc}"))

        if failures:
            self.stdout.write(self.style.ERROR(f"\nCompleted with {failures} failure(s)."))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("\nAll integration checks passed."))
