import requests
from django.conf import settings


class SiteAError(Exception):
    pass


def fetch_materials_catalog():
    """GET the WM Website's live material catalog.

    Returns a list of dicts: [{"id", "name", "quantity", "unit"}, ...]
    """
    resp = requests.get(
        f"{settings.WM_WEBSITE_BASE_URL}/api/inventory/materials/catalog/",
        headers={"X-Site-B-API-Key": settings.WM_WEBSITE_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def submit_request_to_site_a(
    *,
    material_id,
    quantity,
    requester_email,
    justification="",
    webhook_url=None,
):
    """POST a new material request to the WM Website.

    Args:
        material_id:     The WM Website's own material PK (Material.site_a_material_id).
        quantity:        Integer/Decimal quantity being requested.
        requester_email: Email of the PE engineer who raised the request — so the
                         WM warehouse manager can see who submitted it.
        justification:   Free-text reason for the request (maps to our local
                         MaterialRequest.justification field).
        webhook_url:     Full public URL of our receiver endpoint.  Falls back to
                         SITE_B_PUBLIC_WEBHOOK_URL from settings when not provided.

    Returns:
        dict — the WM Website's JSON response, which includes its own "id" for the
        created request record.  This id is stored locally as site_a_request_id.
    """
    payload = {
        "material_id": material_id,
        "quantity": quantity,
        "justification": justification,
        "requester_email": requester_email,
        "webhook_url": webhook_url or settings.SITE_B_PUBLIC_WEBHOOK_URL,
    }
    resp = requests.post(
        f"{settings.WM_WEBSITE_BASE_URL}/api/inventory/requests/create/",
        json=payload,
        headers={"X-Site-B-API-Key": settings.WM_WEBSITE_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
