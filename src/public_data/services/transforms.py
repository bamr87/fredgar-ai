"""FRED unit transforms and frequency aggregation over stored observations (FR-MAC-001).

Pure functions (no ORM, no network), so the API, the commands and the tests share one
implementation of FRED's documented behaviour:

- ``units`` (https://alfred.stlouisfed.org/help#growth_formulas): ``lin``, ``chg``, ``ch1``,
  ``pch``, ``pc1``, ``pca``, ``cch``, ``cca`` and ``log``, where ``n`` is the number of
  observations per year at the output frequency (daily 260, weekly 52, biweekly 26,
  monthly 12, quarterly 4, semiannual 2, annual 1).
- ``frequency`` and ``aggregation`` (https://fred.stlouisfed.org/docs/api/fred/series_observations.html):
  aggregate to a *lower* frequency by average, sum or end of period. Asking for a frequency
  higher than the series' own is an error and asking for its own is a no-op, as in the
  FRED API. Aggregation runs first, then the units transform.

Lags are taken by period, not by position: x(t-1) is the observation one period earlier at
the output frequency (the previous weekday for daily data), and a missing period gives no
value, the way FRED's ``.`` rows do. Ingest drops FRED's ``.`` rows, so counting positions
would compare against the wrong period after any gap.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

UNITS = ("lin", "chg", "ch1", "pch", "pc1", "pca", "cch", "cca", "log")
AGGREGATIONS = ("avg", "sum", "eop")
#: Frequencies a series can be aggregated to, highest first. FRED's biweekly target
#: (``bw``, "Biweekly, Ending Wednesday") is left out: FRED does not document which
#: Wednesdays anchor its two-week periods. A natively biweekly series still transforms.
FREQUENCIES = ("d", "w", "m", "q", "sa", "a")
#: ``n`` in FRED's formulas: observations per year at each frequency.
OBS_PER_YEAR = {"d": 260, "w": 52, "bw": 26, "m": 12, "q": 4, "sa": 2, "a": 1}
_ORDER = ("d", "w", "bw", "m", "q", "sa", "a")  # highest frequency first
# FRED's frequency labels ("Weekly, Ending Friday", "Daily, 7-Day", ...) by leading word.
_LABELS = (
    ("daily", "d"),
    ("weekly", "w"),
    ("biweekly", "bw"),
    ("monthly", "m"),
    ("quarterly", "q"),
    ("semiannual", "sa"),
    ("annual", "a"),
)
_SIX_PLACES = Decimal("0.000001")

Point = tuple[date, Decimal]  # a stored observation
Value = Decimal | float  # a transformed value: exact for levels and differences, float otherwise


class TransformError(ValueError):
    """A transform FRED itself would refuse: an unknown code, or a frequency above the series' own."""


@dataclass(frozen=True)
class Transformed:
    """A transformed series: the frequency it is at, and one value per period (None where undefined)."""

    frequency: str | None
    points: list[tuple[date, Value | None]]


def _check(value: str, allowed: Sequence[str], name: str) -> None:
    if value not in allowed:
        raise TransformError(f"unknown {name} '{value}'; expected one of: {', '.join(allowed)}")


def frequency_code(text: str | None) -> str | None:
    """The FRED frequency code (``m``, ``q``, ...) for a code or a FRED label, else None."""
    label = (text or "").strip().lower()
    if label in OBS_PER_YEAR:
        return label
    for word, code in _LABELS:
        if label.startswith(word):
            return code
    return None


def infer_frequency(dates: Iterable[date]) -> str | None:
    """A series' frequency judged by the median gap between its dates (None for fewer than two)."""
    days = sorted(set(dates))
    if len(days) < 2:
        return None
    gaps = sorted((later - earlier).days for earlier, later in zip(days, days[1:]))
    median = gaps[len(gaps) // 2]
    for code, limit in (("d", 4), ("w", 10), ("bw", 20), ("m", 45), ("q", 135), ("sa", 270)):
        if median <= limit:
            return code
    return "a"


def period_label(day: date, frequency: str) -> date:
    """The date FRED gives the ``frequency`` period that contains ``day``.

    The first day of the month, quarter, half-year or year; for ``w`` the Friday that ends
    the week (FRED's ``w`` is "Weekly, Ending Friday"); for ``d`` the day itself.
    """
    _check(frequency, FREQUENCIES, "frequency")
    if frequency == "d":
        return day
    if frequency == "w":
        return day + timedelta(days=(4 - day.weekday()) % 7)
    if frequency == "m":
        return day.replace(day=1)
    if frequency == "q":
        return date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)
    if frequency == "sa":
        return date(day.year, 1 if day.month <= 6 else 7, 1)
    return date(day.year, 1, 1)


def aggregate(points: Iterable[Point], frequency: str, method: str = "avg") -> list[Point]:
    """Aggregate ``points`` to ``frequency`` by ``method``: ``avg``, ``sum`` or ``eop``.

    ``eop`` (end of period) keeps the last observation in each period. A period still in
    progress aggregates the observations it has so far. ``d`` returns the points unchanged:
    daily is the highest frequency, so there is nothing to aggregate.
    """
    _check(frequency, FREQUENCIES, "frequency")
    _check(method, AGGREGATIONS, "aggregation")
    groups: dict[date, list[Decimal]] = {}
    for day, value in sorted(points):
        groups.setdefault(period_label(day, frequency), []).append(value)
    out: list[Point] = []
    for label, values in groups.items():
        if method == "eop":
            out.append((label, values[-1]))
            continue
        total = values[0]
        for value in values[1:]:
            total += value
        out.append((label, total if method == "sum" else total / len(values)))
    return out


def _period_index(day: date, frequency: str, calendar_days: bool) -> int:
    """Consecutive integers for consecutive periods, so x(t-k) sits at index - k."""
    if frequency == "a":
        return day.year
    if frequency == "sa":
        return day.year * 2 + (day.month - 1) // 6
    if frequency == "q":
        return day.year * 4 + (day.month - 1) // 3
    if frequency == "m":
        return day.year * 12 + day.month - 1
    if frequency == "bw":
        return day.toordinal() // 14
    if frequency == "w":
        return day.toordinal() // 7
    if calendar_days:  # a 7-day daily series
        return day.toordinal()
    week, weekday = divmod(day.toordinal() - 1, 7)  # date(1, 1, 1) is a Monday
    return week * 5 + weekday  # weekdays only: FRED's daily year is 260 observations


def _ln(value: Decimal) -> float | None:
    return math.log(float(value)) if value > 0 else None


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def _unit_value(units: str, x: Decimal, prev: Decimal, n: int) -> Value | None:
    """FRED's formula for ``units`` given x(t) and the lagged x(t-1) or x(t-n)."""
    if units in ("chg", "ch1"):
        return x - prev
    if units in ("cch", "cca"):
        ln_x, ln_prev = _ln(x), _ln(prev)
        if ln_x is None or ln_prev is None:
            return None
        rate = (ln_x - ln_prev) * 100
        return _finite(rate * n if units == "cca" else rate)
    if prev == 0:
        return None
    ratio = float(x) / float(prev)
    if units in ("pch", "pc1"):
        return _finite((ratio - 1) * 100)
    try:  # pca: the one-period ratio compounded over a year can exceed a float
        compounded = ratio**n
    except OverflowError:
        return None
    return _finite((compounded - 1) * 100)


def apply_units(
    points: Iterable[Point], units: str, frequency: str | None
) -> list[tuple[date, Value | None]]:
    """FRED's ``units`` transform of ``points``, which are at ``frequency``.

    One (date, value) per point. The value is None where FRED shows ``.``: the lagged
    period is missing, a percentage would divide by zero, or a logarithm meets a value
    that is not positive. ``frequency`` None (unknown, as for a single observation) makes
    every lagged unit None.
    """
    _check(units, UNITS, "units")
    if frequency is not None and frequency not in OBS_PER_YEAR:
        raise TransformError(f"unknown frequency '{frequency}'")
    ordered = sorted(points)
    if units == "lin":
        return list(ordered)
    if units == "log":
        return [(day, _ln(value)) for day, value in ordered]
    if frequency is None:
        return [(day, None) for day, _ in ordered]
    n = OBS_PER_YEAR[frequency]
    lag = n if units in ("ch1", "pc1") else 1
    calendar = frequency == "d" and any(day.weekday() >= 5 for day, _ in ordered)
    by_index = {_period_index(day, frequency, calendar): value for day, value in ordered}
    out: list[tuple[date, Value | None]] = []
    for day, value in ordered:
        prev = by_index.get(_period_index(day, frequency, calendar) - lag)
        out.append((day, None if prev is None else _unit_value(units, value, prev, n)))
    return out


def transform_series(
    points: Iterable[Point],
    *,
    native: str | None,
    units: str = "lin",
    frequency: str | None = None,
    aggregation: str = "avg",
    strict: bool = True,
) -> Transformed:
    """Aggregate to ``frequency`` when it is lower than the series' own, then apply ``units``.

    ``native`` is the series' own frequency code, inferred from the dates when None.
    Asking for a frequency higher than that raises TransformError when ``strict`` (FRED's
    behaviour, used for a single series); otherwise the series keeps its own frequency, since
    one request against a bundle that mixes daily and quarterly series cannot be lower than
    all of them.
    """
    ordered = sorted(points)
    own = native or infer_frequency(day for day, _ in ordered)
    out_frequency = own
    if frequency is not None:
        _check(frequency, FREQUENCIES, "frequency")
        if own is not None and _ORDER.index(frequency) < _ORDER.index(own):
            if strict:
                raise TransformError(
                    f"frequency '{frequency}' is higher than the series' own frequency "
                    f"'{own}'; FRED only aggregates to a lower frequency"
                )
        elif frequency != own:
            ordered = aggregate(ordered, frequency, aggregation)
            out_frequency = frequency
    return Transformed(out_frequency, apply_units(ordered, units, out_frequency))


def format_value(value: Value) -> str:
    """A value as the API's decimal string, with at most six decimal places (the stored precision)."""
    number = value if isinstance(value, Decimal) else Decimal(repr(float(value)))
    exponent = number.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -6:
        number = number.quantize(_SIX_PLACES)
    if number.is_zero():
        number = number.copy_abs()
    return str(number)
