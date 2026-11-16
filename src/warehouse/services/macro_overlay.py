"""Company metric vs macro series overlay (FREDGAR-013, FR-ANL-002).

Aligns a company series (an XBRL concept chain or a ``DerivedMetric`` key) with a
stored FRED series over the company's own fiscal periods, and summarises how the
two move together with a Pearson correlation.

DB-first: it reads stored ``Fact``, ``DerivedMetric`` and ``SeriesObservation``
rows only and never calls SEC or FRED. A series that has not been synced is
reported as missing (the API answers ``404``); sync it with
``refresh_series_bundles`` or ``sync_series_bundle`` first.

Alignment, as documented in ``docs/api-and-cli.md``:

* **Fiscal windows, not calendar windows.** Each company value covers a window
  ``[start, end]``. A durational fact uses its own ``period_start`` and
  ``period_end``. A derived metric takes the window of the longest durational
  input fact reported for that ``period_end``, the same fact
  ``compute_derived_metrics`` resolves. A point-in-time value with no duration
  (an instant fact such as ``Assets``, or a balance-sheet-only metric) covers one
  fiscal period: the span since the series' previous ``period_end``, and for the
  earliest such value the same length as the period after it.
* **Observations by date.** A series observation belongs to the window its
  ``observation_date`` falls in. FRED labels a period by its first day, so a
  June fiscal year (July to June) takes the twelve monthly observations dated
  July 1 through June 1, or the four quarterly ones dated July 1 through April 1.
* **Aggregation.** ``avg`` (default) is the mean of those observations; ``eop``
  is the last one.
* **Partly covered windows are dropped,** never padded or interpolated: the
  first observation must fall within one series step of the window start, the
  last within one step of its end, and no two consecutive observations may be
  more than 1.5 steps apart. The step is the median spacing of the series'
  stored observations, and every bound has three days of slack for weekends and
  holidays. Dropped windows are listed with the reason.
* **Correlation.** Pearson r over the aligned pairs, ``null`` when fewer than
  three pairs align or either side is constant.
"""

from __future__ import annotations

import bisect
import itertools
import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db.models import Min

from public_data.models import ExternalSeries, SeriesObservation
from sec_edgar.reference_data import concept_groups_ordered, derived_kpi_definitions
from warehouse.models import Company, DerivedMetric, Fact
from warehouse.services.edgar.analytics import EdgarAnalyticsService

AGGREGATIONS = ("avg", "eop")
DEFAULT_AGGREGATION = "avg"
MIN_CORRELATION_N = 3
# A durational value shorter than this is sub-annual (matches ``timeseries_for_concepts``).
ANNUAL_MIN_DAYS = 300
# Slack on every coverage bound, for weekends, holidays and month-length differences.
SLACK_DAYS = 3
# Consecutive observations further apart than this many steps mean a missing one.
GAP_STEPS = 1.5

ALIGNMENT_DESCRIPTION = (
    "Each company value covers its fiscal window [period_start, period_end]: a durational "
    "fact's own period; a derived metric's longest durational input fact for that period end; "
    "a point-in-time value the span since the previous period end. The series observations "
    "dated inside the window are aggregated (avg = mean, eop = last). A window the series does "
    "not fully cover is dropped: the first observation must fall within one series step of the "
    "start, the last within one step of the end, and no gap may exceed 1.5 steps (3 days slack "
    "on each bound). Pearson r is computed over the aligned pairs and is null when n < 3."
)


@dataclass(frozen=True)
class CompanyPoint:
    """One company observation: its value and the fiscal window it covers."""

    period_end: date
    value: float
    period_start: date | None = None


def known_metric_keys() -> list[str]:
    """``DerivedMetric`` keys the financial model defines (the valid ``metric`` values)."""
    return sorted(derived_kpi_definitions())


def find_stored_series(series_id: str) -> ExternalSeries | None:
    """The registered series with this external id that has stored observations, or None.

    The id matches case-insensitively; a FRED series wins over another provider's
    series with the same id. Never calls FRED.
    """
    sid = (series_id or "").strip()
    if not sid:
        return None
    candidates = ExternalSeries.objects.filter(
        external_id__iexact=sid, observations__isnull=False
    ).distinct()
    return candidates.filter(provider="fred").first() or candidates.order_by("provider", "id").first()


def company_points_for_concepts(
    company: Company,
    concepts: list[str],
    *,
    taxonomy: str = "us-gaap",
    annual_only: bool = False,
    limit: int = 80,
) -> tuple[list[CompanyPoint], str | None]:
    """The concept chain's series (oldest first) and its unit, via ``timeseries_for_concepts``."""
    rows = EdgarAnalyticsService.timeseries_for_concepts(
        company, concepts, taxonomy=taxonomy, limit=limit, annual_only=annual_only
    )
    points = [
        CompanyPoint(
            period_end=date.fromisoformat(r["period_end"]),
            value=float(r["value"]),
            period_start=date.fromisoformat(r["period_start"]) if r["period_start"] else None,
        )
        for r in rows
        if r["period_end"] and r["value"] is not None
    ]
    points.sort(key=lambda p: p.period_end)
    unit = next((r["unit"] for r in rows if r.get("unit")), None)
    return points, unit


def company_points_for_metric(
    company: Company,
    key: str,
    *,
    taxonomy: str = "us-gaap",
    annual_only: bool = False,
    limit: int = 80,
) -> tuple[list[CompanyPoint], str | None]:
    """A ``DerivedMetric`` series (oldest first) and its unit.

    A metric row has no ``period_start``. Its window is the one of the longest
    durational input fact reported for that ``period_end``, the fact
    ``compute_derived_metrics`` resolves (longest duration wins). A metric with
    no durational input keeps ``period_start=None`` and is windowed later as a
    point-in-time value. ``annual_only`` drops windows shorter than 300 days.
    """
    by_end: dict[date, float] = {}
    unit: str | None = None
    for m in DerivedMetric.objects.filter(
        company=company, key=key, period_end__isnull=False, value__isnull=False
    ).order_by("-period_end", "-id"):
        if m.period_end is None or m.value is None or m.period_end in by_end:
            continue
        by_end[m.period_end] = float(m.value)
        unit = unit or m.unit or None
    if not by_end:
        return [], None

    input_concepts = {c for chain in concept_groups_ordered().values() for c in chain}
    starts: dict[date, date] = {}
    for row in (
        Fact.objects.filter(
            company=company,
            taxonomy=taxonomy,
            concept__in=input_concepts,
            period_end__in=list(by_end),
            period_start__isnull=False,
            value__isnull=False,
        )
        .values("period_end")
        .annotate(start=Min("period_start"))
    ):
        if row["period_end"] is not None and row["start"] is not None:
            starts[row["period_end"]] = row["start"]

    points: list[CompanyPoint] = []
    for end in sorted(by_end, reverse=True):
        start = starts.get(end)
        if annual_only and start is not None and (end - start).days < ANNUAL_MIN_DAYS:
            continue
        points.append(CompanyPoint(period_end=end, value=by_end[end], period_start=start))
        if len(points) >= limit:
            break
    points.sort(key=lambda p: p.period_end)
    return points, unit


def fiscal_windows(points: list[CompanyPoint]) -> list[tuple[CompanyPoint, date | None]]:
    """Pair each point (oldest first) with the start of the fiscal window it covers.

    A point with a ``period_start`` keeps it. A point-in-time value covers the
    span since the previous point's ``period_end``; the earliest one covers the
    same length as the window after it. A lone point-in-time value has no window
    (``None``).
    """
    starts: list[date | None] = []
    for i, p in enumerate(points):
        if p.period_start is not None:
            starts.append(p.period_start)
        elif i > 0:
            starts.append(points[i - 1].period_end + timedelta(days=1))
        else:
            starts.append(None)
    if len(points) > 1 and starts[0] is None and starts[1] is not None:
        # Same number of days as the next window: [end - (next_end - next_start), end].
        starts[0] = points[0].period_end - (points[1].period_end - starts[1])
    return list(zip(points, starts, strict=True))


def series_step_days(dates: list[date]) -> float | None:
    """The series' native step: the median spacing of its (sorted) observation dates."""
    if len(dates) < 2:
        return None
    return float(statistics.median((b - a).days for a, b in itertools.pairwise(dates)))


def window_observations(
    dates: list[date], values: list[float], start: date, end: date, step: float
) -> tuple[list[float], str | None]:
    """The series values dated inside ``[start, end]``, or a reason the window is not covered."""
    lo = bisect.bisect_left(dates, start)
    hi = bisect.bisect_right(dates, end)
    if lo == hi:
        return [], "no_observations"
    if (dates[lo] - start).days > step + SLACK_DAYS:
        return [], "series_starts_late"
    if (end - dates[hi - 1]).days > step + SLACK_DAYS:
        return [], "series_ends_early"
    max_gap = step * GAP_STEPS + SLACK_DAYS
    if any((b - a).days > max_gap for a, b in itertools.pairwise(dates[lo:hi])):
        return [], "gap"
    return values[lo:hi], None


def aggregate(values: list[float], agg: str) -> float:
    """``avg`` = arithmetic mean; ``eop`` = the last value (end of period)."""
    if agg == "eop":
        return values[-1]
    return math.fsum(values) / len(values)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson r of two equal-length samples; None when n < 3 or either side is constant."""
    n = len(xs)
    if n < MIN_CORRELATION_N or n != len(ys):
        return None
    mx = math.fsum(xs) / n
    my = math.fsum(ys) / n
    sxx = math.fsum((x - mx) ** 2 for x in xs)
    syy = math.fsum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    return max(-1.0, min(1.0, sxy / math.sqrt(sxx * syy)))


def build_macro_overlay(
    company: Company,
    series: ExternalSeries,
    *,
    metric: str | None = None,
    concepts: list[str] | None = None,
    agg: str = DEFAULT_AGGREGATION,
    annual_only: bool = False,
    taxonomy: str = "us-gaap",
    limit: int = 80,
) -> dict[str, Any]:
    """Aligned company and series values per fiscal window, with Pearson r.

    Give exactly one of ``metric`` (a ``DerivedMetric`` key) or ``concepts`` (an
    XBRL concept priority chain). Raises ``ValueError`` on an unknown ``agg`` or
    ``metric``, or when neither or both are given.
    """
    if agg not in AGGREGATIONS:
        raise ValueError(f"Unknown agg '{agg}'; use one of: {', '.join(AGGREGATIONS)}.")
    if bool(metric) == bool(concepts):
        raise ValueError("Give exactly one of metric or concept.")
    if metric:
        if metric not in derived_kpi_definitions():
            raise ValueError(f"Unknown metric '{metric}'.")
        points, unit = company_points_for_metric(
            company, metric, taxonomy=taxonomy, annual_only=annual_only, limit=limit
        )
        company_series: dict[str, Any] = {"source": "metric", "key": metric, "concepts": None}
    else:
        chain = list(concepts or [])
        points, unit = company_points_for_concepts(
            company, chain, taxonomy=taxonomy, annual_only=annual_only, limit=limit
        )
        company_series = {"source": "concept", "key": chain[0], "concepts": chain}
    company_series.update({"taxonomy": taxonomy, "unit": unit, "annual": annual_only})

    obs = list(
        SeriesObservation.objects.filter(series=series)
        .order_by("observation_date")
        .values_list("observation_date", "value")
    )
    dates = [d for d, _v in obs]
    values = [float(v) for _d, v in obs]
    step = series_step_days(dates)

    rows: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for point, start in fiscal_windows(points):
        window: list[float] = []
        reason: str | None
        if start is None:
            reason = "no_fiscal_window"
        elif step is None:
            reason = "series_too_short"
        else:
            window, reason = window_observations(dates, values, start, point.period_end, step)
        if reason:
            dropped.append(
                {
                    "period_start": start.isoformat() if start else None,
                    "period_end": point.period_end.isoformat(),
                    "reason": reason,
                }
            )
            continue
        rows.append(
            {
                "period_start": start.isoformat() if start else None,
                "period_end": point.period_end.isoformat(),
                "company_value": point.value,
                "series_value": aggregate(window, agg),
                "series_observations": len(window),
            }
        )

    r = pearson([row["company_value"] for row in rows], [row["series_value"] for row in rows])
    return {
        "company": company.id,
        "company_series": company_series,
        "series": {
            "external_id": series.external_id,
            "provider": series.provider,
            "title": series.title,
            "units": series.units,
            "frequency": series.frequency,
        },
        "alignment": {
            "window": "fiscal",
            "aggregation": agg,
            "series_step_days": step,
            "description": ALIGNMENT_DESCRIPTION,
            "dropped": dropped,
        },
        "rows": rows,
        "correlation": {"method": "pearson", "r": r, "n": len(rows)},
    }
