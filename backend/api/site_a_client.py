import requests
from django.conf import settings

class SiteAError(Exception):
    pass

def fetch_materials_catalog():
    """GET Website 1's material catalog."""
    resp = requests.get(
        f"{settings.SITE_A_BASE_URL}/api/inventory/materials/catalog/",
        headers={"X-Site-B-API-Key": settings.SITE_A_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

def submit_request_to_site_a(*, material_id, requester_id, requester_email, quantity, reason=""):
    """POST a new material request to Website 1. Returns Website 1's response dict, including its own `id`."""
    payload = {
        "material": material_id,
        "requester_id": str(requester_id),
        "requester_email": requester_email,
        "quantity": str(quantity),
        "reason": reason,
        "webhook_url": settings.SITE_B_PUBLIC_WEBHOOK_URL,
    }
    resp = requests.post(
        f"{settings.SITE_A_BASE_URL}/api/inventory/requests/create/",
        json=payload,
        headers={"X-Site-B-API-Key": settings.SITE_A_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
