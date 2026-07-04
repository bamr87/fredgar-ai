"""Build-time context for the static site's macro (FRED) section.

Everything here reads only what's already in the warehouse (``SeriesBundle`` /
``ExternalSeries`` / ``SeriesObservation``) — no FRED API calls. The static-site
generator renders the returned dicts into plain HTML/CSV/JSON, so the published
mirror needs no backend and never fetches at view time.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from public_data.models import SeriesBundle, SeriesObservation

# Rendering windows: sparkline/table cover recent history; the CSV export carries
# every observation synced into the warehouse.
SPARK_YEARS = 5
SPARK_MAX_POINTS = 160
TABLE_ROWS = 12

FRED_SERIES_URL = "https://fred.stlouisfed.org/series/"


def macro_data_available() -> bool:
    """True when at least one bundled series has observations to publish."""
    return SeriesObservation.objects.filter(series__bundle_items__isnull=False).exists()


def fmt_obs_value(value: Any) -> str:
    """Format an observation value: grouped, up to 2 decimals, trailing zeros trimmed."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    text = f"{v:,.2f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _delta(latest: Decimal, past: Decimal | None) -> dict[str, Any] | None:
    if past is None:
        return None
    diff = latest - past
    return {
        "value": float(diff),
        "display": ("+" if diff > 0 else "") + fmt_obs_value(diff),
        "direction": "up" if diff > 0 else ("down" if diff < 0 else "flat"),
    }


def _sparkline(
    rows: list[tuple[datetime.date, Decimal]], width: int = 240, height: int = 48
) -> str:
    """SVG polyline points for the recent window — server-rendered, no JS needed."""
    if len(rows) < 2:
        return ""
    if len(rows) > SPARK_MAX_POINTS:
        stride = len(rows) / SPARK_MAX_POINTS
        sampled = [rows[int(i * stride)] for i in range(SPARK_MAX_POINTS)]
        sampled[-1] = rows[-1]  # always end on the latest observation
        rows = sampled
    values = [float(v) for _, v in rows]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pad = 2
    step = (width - 2 * pad) / (len(values) - 1)
    return " ".join(
        f"{pad + i * step:.1f},{pad + (height - 2 * pad) * (1 - (v - lo) / span):.1f}"
        for i, v in enumerate(values)
    )


def _series_context(series, today: datetime.date) -> dict[str, Any]:
    window_start = today - datetime.timedelta(days=SPARK_YEARS * 365)
    recent = list(
        SeriesObservation.objects.filter(series=series, observation_date__gte=window_start)
        .order_by("observation_date")
        .values_list("observation_date", "value")
    )
    meta = series.metadata or {}
    ctx: dict[str, Any] = {
        "id": series.external_id,
        "title": series.title or series.external_id,
        "frequency": series.frequency or meta.get("frequency_hint", ""),
        "units": series.units,
        "note": meta.get("note", ""),
        "industries": meta.get("industries", []),
        "fred_url": f"{FRED_SERIES_URL}{series.external_id}",
        "observation_count": SeriesObservation.objects.filter(series=series).count(),
        "last_synced": series.last_synced_at.date().isoformat() if series.last_synced_at else "",
        "latest": None,
        "delta_1m": None,
        "delta_1y": None,
        "spark_points": _sparkline(recent),
        "table": [],
    }
    if not recent:
        return ctx

    latest_date, latest_value = recent[-1]

    def value_at_or_before(target: datetime.date) -> Decimal | None:
        for d, v in reversed(recent):
            if d <= target:
                return v
        return None

    ctx["latest"] = {
        "date": latest_date.isoformat(),
        "value": str(latest_value),
        "display": fmt_obs_value(latest_value),
    }
    ctx["delta_1m"] = _delta(
        latest_value, value_at_or_before(latest_date - datetime.timedelta(days=30))
    )
    ctx["delta_1y"] = _delta(
        latest_value, value_at_or_before(latest_date - datetime.timedelta(days=365))
    )
    ctx["table"] = [
        {"date": d.isoformat(), "value": str(v), "display": fmt_obs_value(v)}
        for d, v in reversed(recent[-TABLE_ROWS:])
    ]
    return ctx


def build_macro_context(today: datetime.date | None = None) -> list[dict[str, Any]]:
    """One dict per bundle that has any observations, in slug order.

    Bundles whose series were never synced are omitted so the static site never
    publishes an empty shell page.
    """
    today = today or datetime.date.today()
    bundles = []
    for bundle in SeriesBundle.objects.order_by("slug").prefetch_related("items__series"):
        series_list = [_series_context(item.series, today) for item in bundle.items.all()]
        series_list = [s for s in series_list if s["latest"]]
        if not series_list:
            continue
        bundles.append(
            {
                "slug": bundle.slug,
                "name": bundle.name,
                "description": bundle.description,
                "href": f"macro/{bundle.slug}/index.html",
                "series": series_list,
            }
        )
    return bundles


def iter_bundle_observations(slug: str):
    """Yield ``(series_id, date, value)`` for every stored observation in a bundle —
    the long-format rows behind the per-bundle CSV export."""
    qs = (
        SeriesObservation.objects.filter(series__bundle_items__bundle__slug=slug)
        .order_by("series__external_id", "observation_date")
        .values_list("series__external_id", "observation_date", "value")
    )
    for series_id, d, v in qs.iterator(chunk_size=2000):
        yield series_id, d.isoformat(), v
