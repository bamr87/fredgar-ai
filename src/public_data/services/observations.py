"""Series observations for the API, FRED-transformed or as of a vintage (FR-MAC-001).

The observation endpoints stay thin: they turn the query into a ``SeriesTransform`` with
``parse_series_transform`` and call ``transformed_observations``, which reads the stored
observations (or the stored ALFRED vintage, fetched once when missing) and applies
``public_data.services.transforms``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from public_data.models import ExternalSeries, SeriesObservation
from public_data.services.transforms import (
    AGGREGATIONS,
    FREQUENCIES,
    UNITS,
    Transformed,
    TransformError,
    format_value,
    frequency_code,
    transform_series,
)
from public_data.services.vintages import check_vintage_date, vintage_points


@dataclass(frozen=True)
class SeriesTransform:
    """What a request asked for. ``aggregation`` is None without a ``frequency`` (FRED ignores it then)."""

    units: str = "lin"
    frequency: str | None = None
    aggregation: str | None = None
    vintage_date: date | None = None

    def echo(self) -> dict:
        """The applied parameters, as the endpoints echo them back."""
        return {
            "units": self.units,
            "frequency": self.frequency,
            "aggregation": self.aggregation,
            "vintage_date": self.vintage_date.isoformat() if self.vintage_date else None,
        }


def _choice(raw: str | None, allowed: tuple[str, ...], name: str) -> str | None:
    value = (raw or "").strip().lower()
    if not value:
        return None
    if value not in allowed:
        raise TransformError(f"unknown {name} '{value}'; expected one of: {', '.join(allowed)}")
    return value


def parse_series_transform(
    *,
    units: str | None = None,
    frequency: str | None = None,
    aggregation: str | None = None,
    vintage_date: str | None = None,
) -> SeriesTransform | None:
    """The transform a request asks for, validated; None when it names none of the four.

    None lets an endpoint answer exactly as it did before the parameters existed. Raises
    TransformError, worded for a 400 ``detail``, on an unknown code, and VintageError (a
    TransformError) on a malformed or future ``vintage_date`` or one sent while
    ``ENABLE_FRED_VINTAGES`` is off.
    """
    if not any((raw or "").strip() for raw in (units, frequency, aggregation, vintage_date)):
        return None
    chosen_units = _choice(units, UNITS, "units") or "lin"
    chosen_frequency = _choice(frequency, FREQUENCIES, "frequency")
    chosen_aggregation = _choice(aggregation, AGGREGATIONS, "aggregation")
    raw_vintage = (vintage_date or "").strip()
    as_of = check_vintage_date(raw_vintage) if raw_vintage else None
    return SeriesTransform(
        units=chosen_units,
        frequency=chosen_frequency,
        aggregation=(chosen_aggregation or "avg") if chosen_frequency else None,
        vintage_date=as_of,
    )


def native_frequency(series: ExternalSeries) -> str | None:
    """The series' own frequency code from FRED's metadata or the bundle hint (None: infer it)."""
    meta = series.metadata or {}
    fred = meta.get("fred") or {}
    for candidate in (fred.get("frequency_short"), series.frequency, meta.get("frequency_hint")):
        code = frequency_code(candidate)
        if code:
            return code
    return None


def series_points(
    series: ExternalSeries, vintage: date | None = None, *, fetch_missing: bool = False
) -> list[tuple[date, Decimal]]:
    """The stored observations of ``series``, oldest first, or its vintage as of ``vintage``.

    ``fetch_missing`` lets a vintage that is not stored be fetched from FRED.
    """
    if vintage is not None:
        return vintage_points(series, vintage, fetch_missing=fetch_missing)
    rows = SeriesObservation.objects.filter(series=series).order_by("observation_date")
    return list(rows.values_list("observation_date", "value"))


def transformed_observations(
    series: ExternalSeries, transform: SeriesTransform, *, strict: bool, fetch_missing: bool
) -> Transformed:
    """``series`` with ``transform`` applied: aggregation first, then units, as FRED does.

    ``strict`` refuses a frequency above the series' own (one series); otherwise the
    series keeps its own frequency (a bundle). ``fetch_missing`` lets a missing vintage be
    fetched from FRED. Raises VintageUnavailable (VintageNotStored when it may not be
    fetched) when a vintage is neither stored nor fetchable.
    """
    return transform_series(
        series_points(series, transform.vintage_date, fetch_missing=fetch_missing),
        native=native_frequency(series),
        units=transform.units,
        frequency=transform.frequency,
        aggregation=transform.aggregation or "avg",
        strict=strict,
    )


def newest_first(result: Transformed) -> list[tuple[date, str]]:
    """The defined values as API strings, newest first; undefined ones (FRED's ``.``) are left out."""
    return [(day, format_value(value)) for day, value in reversed(result.points) if value is not None]
