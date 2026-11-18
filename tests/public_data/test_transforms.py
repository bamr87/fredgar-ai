"""FRED units and frequency aggregation against FRED's documented formulas (FR-MAC-001).

Expected values are worked by hand from https://alfred.stlouisfed.org/help#growth_formulas
(n = observations per year: monthly 12, quarterly 4, weekly 52, daily 260).
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest

from public_data.services.transforms import (
    TransformError,
    aggregate,
    apply_units,
    format_value,
    frequency_code,
    infer_frequency,
    transform_series,
)

# 2023-01 .. 2023-12 = 100 .. 111, then 2024-01 .. 2024-03 = 112 .. 114.
MONTHLY = [(date(2023, m, 1), Decimal(99 + m)) for m in range(1, 13)] + [
    (date(2024, m, 1), Decimal(111 + m)) for m in range(1, 4)
]
# Six quarters, 2022Q1 .. 2023Q2.
QUARTERLY = [
    (date(2022, 1, 1), Decimal(200)),
    (date(2022, 4, 1), Decimal(202)),
    (date(2022, 7, 1), Decimal(204)),
    (date(2022, 10, 1), Decimal(206)),
    (date(2023, 1, 1), Decimal(210)),
    (date(2023, 4, 1), Decimal(212)),
]


def values(points):
    return {d: (None if v is None else float(v)) for d, v in points}


# --------------------------------------------------------------------------- units: monthly


def test_lin_is_the_identity():
    assert apply_units(MONTHLY, "lin", "m") == MONTHLY


def test_chg_is_the_one_period_difference():
    out = values(apply_units(MONTHLY, "chg", "m"))
    assert out[date(2023, 1, 1)] is None  # no x(t-1)
    assert out[date(2023, 2, 1)] == 1.0
    assert out[date(2024, 1, 1)] == 1.0  # across the year boundary


def test_ch1_is_the_difference_from_a_year_ago():
    out = values(apply_units(MONTHLY, "ch1", "m"))
    assert all(out[date(2023, m, 1)] is None for m in range(1, 13))
    assert out[date(2024, 1, 1)] == 12.0  # 112 - 100
    assert out[date(2024, 3, 1)] == 12.0  # 114 - 102


def test_pch_is_the_one_period_percent_change():
    out = values(apply_units(MONTHLY, "pch", "m"))
    assert out[date(2023, 2, 1)] == pytest.approx(1.0)  # (101/100 - 1) * 100
    assert out[date(2024, 1, 1)] == pytest.approx(0.9009009009)  # (112/111 - 1) * 100


def test_pc1_is_the_percent_change_from_a_year_ago():
    out = values(apply_units(MONTHLY, "pc1", "m"))
    assert out[date(2023, 12, 1)] is None
    assert out[date(2024, 1, 1)] == pytest.approx(12.0)  # (112/100 - 1) * 100
    assert out[date(2024, 3, 1)] == pytest.approx(11.7647058824)  # (114/102 - 1) * 100


def test_pca_compounds_the_monthly_ratio_over_twelve_months():
    out = values(apply_units(MONTHLY, "pca", "m"))
    # ((101/100) ** 12 - 1) * 100
    assert out[date(2023, 2, 1)] == pytest.approx(12.6825030132)


def test_cch_and_cca_are_continuously_compounded():
    cch = values(apply_units(MONTHLY, "cch", "m"))
    cca = values(apply_units(MONTHLY, "cca", "m"))
    assert cch[date(2023, 2, 1)] == pytest.approx(0.9950330853)  # (ln 101 - ln 100) * 100
    assert cca[date(2023, 2, 1)] == pytest.approx(11.9403970238)  # cch * 12
    assert cch[date(2023, 1, 1)] is None


def test_log_is_the_natural_log():
    out = values(apply_units(MONTHLY, "log", "m"))
    assert out[date(2023, 1, 1)] == pytest.approx(4.6051701860)  # ln 100
    assert out[date(2024, 3, 1)] == pytest.approx(math.log(114))


# --------------------------------------------------------------------------- units: quarterly


def test_quarterly_units_use_four_observations_per_year():
    pc1 = values(apply_units(QUARTERLY, "pc1", "q"))
    pca = values(apply_units(QUARTERLY, "pca", "q"))
    cca = values(apply_units(QUARTERLY, "cca", "q"))
    ch1 = values(apply_units(QUARTERLY, "ch1", "q"))
    assert pc1[date(2022, 10, 1)] is None
    assert pc1[date(2023, 1, 1)] == pytest.approx(5.0)  # (210/200 - 1) * 100
    assert pc1[date(2023, 4, 1)] == pytest.approx(4.9504950495)  # (212/202 - 1) * 100
    assert pca[date(2022, 4, 1)] == pytest.approx(4.060401)  # ((202/200) ** 4 - 1) * 100
    assert cca[date(2022, 4, 1)] == pytest.approx(3.9801323413)  # (ln 202 - ln 200) * 100 * 4
    assert ch1[date(2023, 1, 1)] == 10.0


# --------------------------------------------------------------------------- undefined values


def test_a_missing_period_leaves_the_next_change_undefined():
    gappy = [p for p in MONTHLY if p[0] != date(2023, 6, 1)]  # FRED would show '.' for June
    out = values(apply_units(gappy, "chg", "m"))
    assert out[date(2023, 7, 1)] is None
    assert out[date(2023, 8, 1)] == 1.0


def test_percentages_and_logs_are_undefined_where_fred_shows_a_dot():
    points = [(date(2023, 1, 1), Decimal(0)), (date(2023, 2, 1), Decimal(5)), (date(2023, 3, 1), Decimal(-1))]
    pch = values(apply_units(points, "pch", "m"))
    log = values(apply_units(points, "log", "m"))
    cch = values(apply_units(points, "cch", "m"))
    assert pch[date(2023, 2, 1)] is None  # divides by zero
    assert pch[date(2023, 3, 1)] == pytest.approx(-120.0)
    assert log[date(2023, 1, 1)] is None and log[date(2023, 3, 1)] is None
    assert cch[date(2023, 2, 1)] is None and cch[date(2023, 3, 1)] is None


def test_unknown_units_are_refused():
    with pytest.raises(TransformError, match="unknown units"):
        apply_units(MONTHLY, "bogus", "m")


# --------------------------------------------------------------------------- daily lags


def test_daily_lags_count_weekdays():
    # Thu 2024-01-04, Fri 01-05, Mon 01-08: Monday's previous period is Friday.
    points = [(date(2024, 1, 4), Decimal(10)), (date(2024, 1, 5), Decimal(11)), (date(2024, 1, 8), Decimal(13))]
    out = values(apply_units(points, "chg", "d"))
    assert out[date(2024, 1, 5)] == 1.0
    assert out[date(2024, 1, 8)] == 2.0


def test_a_daily_holiday_leaves_the_next_day_undefined():
    # Wed 2024-01-03 missing (a holiday FRED stores as '.').
    points = [(date(2024, 1, 2), Decimal(10)), (date(2024, 1, 4), Decimal(12))]
    assert values(apply_units(points, "chg", "d"))[date(2024, 1, 4)] is None


def test_a_seven_day_series_lags_by_calendar_day():
    points = [(date(2024, 1, 6), Decimal(10)), (date(2024, 1, 7), Decimal(12))]  # Sat, Sun
    assert values(apply_units(points, "chg", "d"))[date(2024, 1, 7)] == 2.0


def test_daily_year_ago_is_260_weekdays_back():
    start = date(2023, 1, 2)  # a Monday
    weekdays = []
    day = start
    while len(weekdays) < 261:
        if day.weekday() < 5:
            weekdays.append(day)
        day += timedelta(days=1)
    points = [(d, Decimal(100 + i)) for i, d in enumerate(weekdays)]
    out = values(apply_units(points, "ch1", "d"))
    assert out[weekdays[259]] is None
    assert out[weekdays[260]] == 260.0  # x(t) - x(t-260)


# --------------------------------------------------------------------------- aggregation


def test_monthly_to_quarterly_by_each_method():
    avg = values(aggregate(MONTHLY, "q", "avg"))
    total = values(aggregate(MONTHLY, "q", "sum"))
    eop = values(aggregate(MONTHLY, "q", "eop"))
    assert list(avg) == [date(2023, 1, 1), date(2023, 4, 1), date(2023, 7, 1), date(2023, 10, 1), date(2024, 1, 1)]
    assert avg[date(2023, 1, 1)] == 101.0  # (100 + 101 + 102) / 3
    assert total[date(2023, 4, 1)] == 312.0  # 103 + 104 + 105
    assert eop[date(2023, 10, 1)] == 111.0
    assert avg[date(2024, 1, 1)] == 113.0


def test_monthly_to_annual_and_semiannual():
    annual = values(aggregate(MONTHLY, "a", "avg"))
    half = values(aggregate(MONTHLY, "sa", "sum"))
    assert annual[date(2023, 1, 1)] == 105.5  # mean of 100 .. 111
    assert annual[date(2024, 1, 1)] == 113.0  # a year in progress: what it has so far
    assert half[date(2023, 1, 1)] == 615.0  # 100 + .. + 105
    assert half[date(2023, 7, 1)] == 651.0  # 106 + .. + 111


def test_daily_to_weekly_ends_on_friday():
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(10)]  # Mon 01-01 .. Wed 01-10
    points = [(d, Decimal(i)) for i, d in enumerate(days) if d.weekday() < 5]
    eop = values(aggregate(points, "w", "eop"))
    assert eop == {date(2024, 1, 5): 4.0, date(2024, 1, 12): 9.0}


def test_unknown_aggregation_is_refused():
    with pytest.raises(TransformError, match="unknown aggregation"):
        aggregate(MONTHLY, "q", "median")


# --------------------------------------------------------------------------- the pipeline


def test_aggregation_runs_before_units():
    result = transform_series(MONTHLY, native="m", units="pc1", frequency="q", aggregation="avg")
    assert result.frequency == "q"
    out = values(result.points)
    assert out[date(2023, 10, 1)] is None
    assert out[date(2024, 1, 1)] == pytest.approx(11.8811881188)  # (113/101 - 1) * 100


def test_a_frequency_above_the_series_own_is_refused_like_fred():
    with pytest.raises(TransformError, match="higher than the series' own frequency"):
        transform_series(QUARTERLY, native="q", frequency="m")


def test_a_bundle_keeps_the_series_own_frequency_instead():
    result = transform_series(QUARTERLY, native="q", frequency="m", strict=False)
    assert result.frequency == "q"
    assert result.points == QUARTERLY


def test_asking_for_the_series_own_frequency_is_a_no_op():
    result = transform_series(MONTHLY, native="m", frequency="m", aggregation="sum")
    assert result.frequency == "m"
    assert result.points == MONTHLY


def test_the_native_frequency_is_inferred_when_unknown():
    assert transform_series(QUARTERLY, native=None, units="pc1").frequency == "q"


# --------------------------------------------------------------------------- helpers


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Monthly", "m"),
        ("Quarterly, End of Period", "q"),
        ("Weekly, Ending Friday", "w"),
        ("Biweekly, Ending Wednesday", "bw"),
        ("Daily, 7-Day", "d"),
        ("Semiannual", "sa"),
        ("Annual", "a"),
        ("SA", "sa"),
        ("m", "m"),
        ("Not Applicable", None),
        ("", None),
        (None, None),
    ],
)
def test_frequency_code(text, code):
    assert frequency_code(text) == code


def test_infer_frequency():
    weekdays = [date(2024, 1, 1) + timedelta(days=i) for i in range(30)]
    assert infer_frequency(d for d in weekdays if d.weekday() < 5) == "d"
    assert infer_frequency(date(2024, 1, 5) + timedelta(weeks=i) for i in range(8)) == "w"
    assert infer_frequency(d for d, _ in MONTHLY) == "m"
    assert infer_frequency(d for d, _ in QUARTERLY) == "q"
    assert infer_frequency(date(2000 + i, 1, 1) for i in range(5)) == "a"
    assert infer_frequency([date(2024, 1, 1)]) is None


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Decimal("4.250000"), "4.250000"),
        (Decimal(5) / Decimal(3), "1.666667"),
        (12.682503013196977, "12.682503"),
        (-0.0, "0.0"),
        (1.4e45, "1.4E+45"),
    ],
)
def test_format_value(value, text):
    assert format_value(value) == text


# --------------------------------------------------------------------------- other frequencies


def test_annual_semiannual_weekly_and_biweekly_lags():
    annual = [(date(2020 + i, 1, 1), Decimal(100 + 10 * i)) for i in range(3)]
    half = [(date(2023, 1, 1), Decimal(50)), (date(2023, 7, 1), Decimal(55)), (date(2024, 1, 1), Decimal(66))]
    weekly = [(date(2024, 1, 6) + timedelta(weeks=i), Decimal(10 + i)) for i in range(3)]  # Saturdays
    biweekly = [(date(2024, 1, 3) + timedelta(weeks=2 * i), Decimal(20 + 2 * i)) for i in range(3)]
    assert values(apply_units(annual, "pca", "a"))[date(2021, 1, 1)] == pytest.approx(10.0)  # n = 1
    assert values(apply_units(half, "pc1", "sa"))[date(2024, 1, 1)] == pytest.approx(32.0)  # 66 vs 50, n = 2
    assert values(apply_units(weekly, "chg", "w"))[date(2024, 1, 13)] == 1.0
    assert values(apply_units(biweekly, "cca", "bw"))[date(2024, 1, 17)] == pytest.approx(
        (math.log(22) - math.log(20)) * 100 * 26
    )


def test_daily_to_monthly_and_a_daily_target_is_a_no_op():
    days = [(date(2024, 1, 30), Decimal(1)), (date(2024, 1, 31), Decimal(3)), (date(2024, 2, 1), Decimal(5))]
    assert values(aggregate(days, "m", "avg")) == {date(2024, 1, 1): 2.0, date(2024, 2, 1): 5.0}
    assert aggregate(days, "d", "sum") == days


def test_a_compounded_rate_too_large_for_a_float_is_undefined():
    points = [(date(2024, 1, 1), Decimal(1)), (date(2024, 1, 2), Decimal(1000000))]
    assert values(apply_units(points, "pca", "d"))[date(2024, 1, 2)] is None  # (1e6) ** 260


def test_an_unknown_frequency_leaves_lagged_units_undefined():
    one = [(date(2024, 1, 1), Decimal(5))]
    assert apply_units(one, "chg", None) == [(date(2024, 1, 1), None)]
    assert transform_series(one, native=None, units="log").frequency is None
    with pytest.raises(TransformError, match="unknown frequency"):
        apply_units(one, "chg", "hourly")
