import logging
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone

from api.models import Material, MaterialRequest
from api.site_a_client import fetch_wm_catalog_for_engineer

logger = logging.getLogger("api")

AI_INSIGHTS_CACHE_TTL = 900


def ai_insights_cache_key(engineer_email: str) -> str:
    return f"ai_inventory_insights_{(engineer_email or '').lower().strip()}"


def get_engineer_scoped_materials(engineer_email: str):
    """
    Resolve materials for an engineer's manager catalog — same WM lookup as wm_catalog_{email}.
    Returns Material queryset scoped to that catalog; empty if WM fetch fails or returns nothing.
    """
    engineer_email = (engineer_email or "").lower().strip()
    if not engineer_email:
        return Material.objects.none()

    try:
        wm_items = fetch_wm_catalog_for_engineer(engineer_email)
    except Exception as exc:
        logger.warning(
            "WM catalog fetch failed for insights scoping (%s): %s",
            engineer_email,
            exc,
        )
        return Material.objects.none()

    if not wm_items:
        return Material.objects.none()

    wm_ids = set()
    names = set()
    for item in wm_items:
        wm_id = item.get("id") if item.get("id") is not None else item.get("site_a_material_id")
        if wm_id is not None:
            try:
                wm_ids.add(int(wm_id))
            except (TypeError, ValueError):
                pass
        name = (item.get("name") or "").strip()
        if name:
            names.add(name)

    filters = Q()
    if wm_ids:
        filters |= Q(site_a_material_id__in=wm_ids)
    if names:
        filters |= Q(name__in=names)
    if not filters:
        return Material.objects.none()

    return Material.objects.filter(filters).distinct()


def compute_ai_inventory_insights(engineer_email: str):
    """
    Compute high-demand and depletion insights scoped to one engineer:
    - Materials: manager catalog via WM (same as wm_catalog_{email})
    - Requests: only this engineer's MaterialRequest rows for those materials
    """
    engineer_email = (engineer_email or "").lower().strip()
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    scoped_materials = get_engineer_scoped_materials(engineer_email)
    scoped_material_ids = list(scoped_materials.values_list("pk", flat=True))

    empty_result = {
        "depletion_warnings": [],
        "high_demand_materials": [],
        "updated_at": now.isoformat(),
    }
    if not scoped_material_ids:
        return empty_result

    engineer_requests = MaterialRequest.objects.filter(
        requested_by__email__iexact=engineer_email,
        request_date__gte=thirty_days_ago,
        material_id__in=scoped_material_ids,
    )

    high_demand = list(
        engineer_requests.values("material__name")
        .annotate(total_requested=Sum("quantity_needed"), count=Count("id"))
        .order_by("-total_requested")[:5]
    )

    depletion_data = []
    for mat in scoped_materials.filter(quantity_available__gt=0):
        req_sum = (
            engineer_requests.filter(material=mat).aggregate(total=Sum("quantity_needed"))["total"]
            or 0
        )

        daily_consumption = req_sum / 30.0
        days_remaining = (
            (mat.quantity_available / daily_consumption) if daily_consumption > 0 else 999.0
        )

        if days_remaining <= 14:
            depletion_data.append(
                {
                    "material_id": mat.id,
                    "material_name": mat.name,
                    "quantity_available": mat.quantity_available,
                    "daily_consumption": round(daily_consumption, 2),
                    "days_remaining": round(days_remaining, 1),
                    "urgency": "critical" if days_remaining <= 5 else "warning",
                }
            )

    return {
        "depletion_warnings": depletion_data,
        "high_demand_materials": high_demand,
        "updated_at": now.isoformat(),
    }


def refresh_ai_inventory_insights_cache(engineer_email: str):
    """Compute engineer-scoped insights and store under ai_inventory_insights_{email}."""
    email = (engineer_email or "").lower().strip()
    insights = compute_ai_inventory_insights(email)
    cache.set(ai_insights_cache_key(email), insights, timeout=AI_INSIGHTS_CACHE_TTL)
    logger.info("Refreshed AI inventory insights cache for %s.", email)
    return insights


def get_ai_inventory_insights(engineer_email: str):
    """
    Return cached insights for this engineer, computing and caching on miss so callers
    do not depend on Celery Beat having run yet.
    """
    email = (engineer_email or "").lower().strip()
    cache_key = ai_insights_cache_key(email)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    return refresh_ai_inventory_insights_cache(email)


def format_insights_for_chatbot(insights):
    """Render insights as markdown for injection into the chatbot system prompt."""
    lines = ["=== AI Inventory Insights (last 30 days) ==="]

    high_demand = insights.get("high_demand_materials") or []
    if high_demand:
        lines.append("\n**High-demand materials:**")
        for item in high_demand:
            name = item.get("material__name", "Unknown")
            total = item.get("total_requested", 0)
            count = item.get("count", 0)
            lines.append(f"- {name}: {total} units requested ({count} requests)")
    else:
        lines.append("\n**High-demand materials:** none in the last 30 days")

    warnings = insights.get("depletion_warnings") or []
    if warnings:
        lines.append("\n**Depletion warnings (≤14 days at current consumption):**")
        for warning in warnings:
            lines.append(
                f"- {warning['material_name']}: {warning['days_remaining']} days remaining "
                f"({warning['urgency']})"
            )
    else:
        lines.append("\n**Depletion warnings:** none")

    updated_at = insights.get("updated_at")
    if updated_at:
        lines.append(f"\n(Updated: {updated_at})")

    return "\n".join(lines)
