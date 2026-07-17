import requests
from django.conf import settings


class SiteAError(Exception):
    pass


def fetch_materials_catalog():
    """GET the WM Website's live material catalog (no engineer filter).

    Returns a list of dicts: [{"id", "name", "quantity", "unit"}, ...]
    """
    resp = requests.get(
        f"{settings.WM_WEBSITE_BASE_URL}/api/inventory/materials/catalog/",
        headers={"X-Site-B-API-Key": settings.WM_WEBSITE_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_wm_catalog_for_engineer(engineer_email: str) -> list:
    """GET the WM Website's material catalog filtered for a specific engineer.

    Passes the engineer's email via the X-Engineer-Email header so the WM
    server can return only the materials belonging to the Warehouse Manager
    who has whitelisted this engineer.  Both sites then mirror the same
    dynamic catalogue.

    Args:
        engineer_email: The PE engineer's email address (from request.user.email).

    Returns:
        list of material dicts: [{"id", "name", "quantity", "unit", ...}, ...]

    Raises:
        SiteAError: if the WM site returns a non-2xx response.
        requests.exceptions.RequestException: on network-level failures.
    """
    resp = requests.get(
        f"{settings.WM_WEBSITE_BASE_URL}/api/inventory/materials/catalog/",
        headers={
            "X-Site-B-API-Key": settings.WM_WEBSITE_API_KEY,
            "X-Engineer-Email": engineer_email,
        },
        timeout=10,
    )
    if not resp.ok:
        raise SiteAError(
            f"WM catalog returned HTTP {resp.status_code} for engineer {engineer_email}."
        )
    data = resp.json()
    # Handle both plain list and paginated {"results": [...]} shapes.
    if isinstance(data, list):
        return data
    return data.get("results", data.get("materials", []))


def check_engineer_status_on_wm(engineer_email: str) -> dict:
    """Check whether an engineer is whitelisted / active on the WM site.

    Calls the WM Team Access Control status endpoint and normalises the
    response to the shape expected by the PE frontend and badge renderer:

        {"connected": bool, "manager_name": str | None}

    Args:
        engineer_email: The PE engineer's email address.

    Returns:
        dict with keys "connected" (bool) and "manager_name" (str or None).
        Never raises — failures are silently mapped to {"connected": False, ...}.
    """
    try:
        resp = requests.get(
            f"{settings.WM_WEBSITE_BASE_URL}/api/inventory/engineer-status/",
            params={"email": engineer_email},
            headers={
                "X-Site-B-API-Key": settings.WM_WEBSITE_API_KEY,
                "X-Engineer-Email": engineer_email,
            },
            timeout=8,
        )
        if resp.ok:
            data = resp.json()
            # WM API is expected to return { "active": true, "manager_name": "..." }
            return {
                "connected": bool(data.get("active", False)),
                "manager_name": data.get("manager_name") or data.get("manager") or None,
            }
        # 404 = not found/not whitelisted; 403 = forbidden.
        return {"connected": False, "manager_name": None}
    except requests.exceptions.RequestException:
        return {"connected": False, "manager_name": None}


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
