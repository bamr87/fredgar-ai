"""Company metric vs macro series overlay: fiscal-window alignment and correlation (FREDGAR-013)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
import responses

from public_data.models import ExternalSeries, SeriesObservation
from warehouse.models import Company, DerivedMetric, Fact
from warehouse.services.macro_overlay import (
    CompanyPoint,
    build_macro_overlay,
    find_stored_series,
    fiscal_windows,
    pearson,
    series_step_days,
    window_observations,
)


def _month(index: int, base_year: int = 2020) -> dt.date:
    """The first day of month ``index`` counted from January of ``base_year``."""
    return dt.date(base_year + index // 12, index % 12 + 1, 1)


def _series(external_id: str, points: list[tuple[dt.date, float]], frequency: str = "Monthly"):
    s = ExternalSeries.objects.create(
        provider="fred", external_id=external_id, title=external_id, frequency=frequency
    )
    SeriesObservation.objects.bulk_create(
        [SeriesObservation(series=s, observation_date=d, value=Decimal(str(v))) for d, v in points]
    )
    return s


def _monthly(external_id: str, months: int, skip: set[int] | None = None):
    """A monthly series from 2020-01-01 whose value is the month's index (0, 1, 2, ...)."""
    return _series(
        external_id, [(_month(i), float(i)) for i in range(months) if i not in (skip or set())]
    )


def _fact(company, start, end, value, concept="Revenues"):
    return Fact.objects.create(
        company=company,
        taxonomy="us-gaap",
        concept=concept,
        period_start=start,
        period_end=end,
        value=Decimal(str(value)),
        unit="USD",
    )


@pytest.fixture
def company(db):
    return Company.objects.create(cik="0000000113", ticker="OVLY", name="Overlay Corp")


@pytest.fixture
def june_fy(company):
    """Four fiscal years ending June 30 (July to June), FY2021 to FY2024."""
    for fy, revenue in zip(range(2021, 2025), (100, 200, 300, 400), strict=True):
        _fact(company, dt.date(fy - 1, 7, 1), dt.date(fy, 6, 30), revenue)
    return company


def test_june_fiscal_year_against_monthly_series_uses_fiscal_not_calendar_windows(june_fy):
    series = _monthly("UNRATE", 60)  # Jan 2020 .. Dec 2024, value = month index
    out = build_macro_overlay(june_fy, series, concepts=["Revenues"])

    rows = out["rows"]
    assert [r["period_end"] for r in rows] == ["2021-06-30", "2022-06-30", "2023-06-30", "2024-06-30"]
    assert rows[0]["period_start"] == "2020-07-01"
    # FY2021 = July 2020 (index 6) .. June 2021 (index 17): mean 11.5, not the
    # calendar-2021 mean (17.5).
    assert [r["series_value"] for r in rows] == [11.5, 23.5, 35.5, 47.5]
    assert all(r["series_observations"] == 12 for r in rows)
    assert [r["company_value"] for r in rows] == [100.0, 200.0, 300.0, 400.0]
    assert out["alignment"]["window"] == "fiscal"
    assert out["alignment"]["aggregation"] == "avg"
    assert out["alignment"]["series_step_days"] == 31.0
    assert "fiscal window" in out["alignment"]["description"]
    assert out["correlation"] == {"method": "pearson", "r": pytest.approx(1.0), "n": 4}


def test_eop_takes_the_last_observation_in_the_fiscal_window(june_fy):
    series = _monthly("UNRATE", 60)
    out = build_macro_overlay(june_fy, series, concepts=["Revenues"], agg="eop")
    assert [r["series_value"] for r in out["rows"]] == [17.0, 29.0, 41.0, 53.0]  # each June


def test_quarterly_series_against_june_fiscal_year(june_fy):
    quarters = [dt.date(2020 + q // 4, (q % 4) * 3 + 1, 1) for q in range(20)]  # 2020Q1 .. 2024Q4
    gdp = _series("GDP", [(d, 1000 + 10 * i) for i, d in enumerate(quarters)], frequency="Quarterly")
    out = build_macro_overlay(june_fy, gdp, concepts=["Revenues"])

    # FY2021 takes 2020Q3, 2020Q4, 2021Q1, 2021Q2 (indexes 2..5): mean 1035.
    assert [r["series_observations"] for r in out["rows"]] == [4, 4, 4, 4]
    assert out["rows"][0]["series_value"] == 1035.0
    assert out["alignment"]["series_step_days"] == pytest.approx(91.5, abs=1)


def test_quarterly_facts_against_monthly_series(company):
    # Fiscal quarters ending in January, April, July and October (Feb-Apr, May-Jul, ...).
    for start, end, value in (
        (dt.date(2022, 2, 1), dt.date(2022, 4, 30), 10),
        (dt.date(2022, 5, 1), dt.date(2022, 7, 31), 20),
        (dt.date(2022, 8, 1), dt.date(2022, 10, 31), 30),
        (dt.date(2022, 11, 1), dt.date(2023, 1, 31), 40),
    ):
        _fact(company, start, end, value)
    series = _monthly("CPIAUCSL", 48)
    out = build_macro_overlay(company, series, concepts=["Revenues"])

    # Feb, Mar, Apr 2022 are indexes 25, 26, 27.
    assert [r["series_value"] for r in out["rows"]] == [26.0, 29.0, 32.0, 35.0]
    assert all(r["series_observations"] == 3 for r in out["rows"])


def test_gaps_and_partly_covered_windows_are_dropped_not_padded(june_fy):
    # Missing November 2021 (index 22, inside FY2022); the series ends in
    # March 2024 (index 50), three months short of FY2024's end.
    series = _monthly("UNRATE", 51, skip={22})
    out = build_macro_overlay(june_fy, series, concepts=["Revenues"])

    assert [r["period_end"] for r in out["rows"]] == ["2021-06-30", "2023-06-30"]
    assert {d["period_end"]: d["reason"] for d in out["alignment"]["dropped"]} == {
        "2022-06-30": "gap",
        "2024-06-30": "series_ends_early",
    }
    assert out["correlation"] == {"method": "pearson", "r": None, "n": 2}


def test_window_before_the_series_starts_is_dropped(june_fy):
    # The series starts in October 2020, three months into FY2021.
    series = _series("LATE", [(_month(i), float(i)) for i in range(9, 60)])
    out = build_macro_overlay(june_fy, series, concepts=["Revenues"])
    assert out["alignment"]["dropped"][0] == {
        "period_start": "2020-07-01",
        "period_end": "2021-06-30",
        "reason": "series_starts_late",
    }
    assert len(out["rows"]) == 3


def _dropped(out) -> dict[str, str]:
    return {d["period_end"]: d["reason"] for d in out["alignment"]["dropped"]}


def test_missing_first_month_of_a_fiscal_year_is_a_gap(june_fy):
    # July 2021 (index 18), the first month of FY2022, is missing. FY2021 ends
    # with June 2021 and keeps all twelve months.
    series = _monthly("UNRATE", 60, skip={18})
    out = build_macro_overlay(june_fy, series, concepts=["Revenues"])

    assert _dropped(out) == {"2022-06-30": "gap"}
    assert [r["period_end"] for r in out["rows"]] == ["2021-06-30", "2023-06-30", "2024-06-30"]
    assert all(r["series_observations"] == 12 for r in out["rows"])
    assert out["correlation"]["n"] == 3


def test_missing_last_month_of_a_fiscal_year_is_a_gap_not_the_next_years(june_fy):
    # June 2021 (index 17), the last month of FY2021, is missing. The hole ends
    # before FY2022 starts, so FY2022 keeps all twelve months.
    series = _monthly("UNRATE", 60, skip={17})
    out = build_macro_overlay(june_fy, series, concepts=["Revenues"])

    assert _dropped(out) == {"2021-06-30": "gap"}
    assert [r["period_end"] for r in out["rows"]] == ["2022-06-30", "2023-06-30", "2024-06-30"]
    assert all(r["series_observations"] == 12 for r in out["rows"])


def test_missing_first_quarter_of_a_fiscal_year_is_a_gap(june_fy):
    quarters = [dt.date(2020 + q // 4, (q % 4) * 3 + 1, 1) for q in range(20)]  # 2020Q1 .. 2024Q4
    quarters.remove(dt.date(2021, 7, 1))  # FY2022's first quarter
    gdp = _series("GDP", [(d, 1000.0) for d in quarters], frequency="Quarterly")
    out = build_macro_overlay(june_fy, gdp, concepts=["Revenues"])

    assert _dropped(out) == {"2022-06-30": "gap"}
    assert [r["series_observations"] for r in out["rows"]] == [4, 4, 4]


def test_series_starting_one_month_into_the_first_window_starts_late(june_fy):
    # The series starts in August 2020 (index 7), one month into FY2021.
    series = _series("LATE", [(_month(i), float(i)) for i in range(7, 60)])
    out = build_macro_overlay(june_fy, series, concepts=["Revenues"])

    assert _dropped(out) == {"2021-06-30": "series_starts_late"}
    assert [r["period_end"] for r in out["rows"]] == ["2022-06-30", "2023-06-30", "2024-06-30"]


def test_window_starting_between_two_observations_is_covered():
    # A monthly series dated on the 1st; the window rule assigns observations by date.
    dates = [_month(i) for i in range(24)]
    values = [float(i) for i in range(24)]
    step = series_step_days(dates)
    assert step == 31.0

    # Starts on 2 July: the first observation inside is 1 August, 30 days in, and
    # the one before it (1 July) is a normal step earlier, so nothing is missing.
    window, reason = window_observations(
        dates, values, dt.date(2020, 7, 2), dt.date(2021, 7, 1), step
    )
    assert reason is None
    assert window == [float(i) for i in range(7, 19)]

    # Starts on 15 July with July missing: 1 July is not dated inside the window,
    # so the window still has every observation it should.
    holed = [d for d in dates if d != dt.date(2020, 7, 1)]
    held = [float(d.month - 1 + 12 * (d.year - 2020)) for d in holed]
    window, reason = window_observations(
        holed, held, dt.date(2020, 7, 15), dt.date(2021, 6, 30), step
    )
    assert reason is None
    assert len(window) == 11  # 1 August 2020 .. 1 June 2021

    # Starts on 1 July with July missing: that observation is dated inside it.
    window, reason = window_observations(
        holed, held, dt.date(2020, 7, 1), dt.date(2021, 6, 30), step
    )
    assert (window, reason) == ([], "gap")


def test_known_pearson_r(company):
    # Calendar fiscal years against an annual series: one observation per window.
    for year, value in zip(range(2019, 2024), (1, 2, 3, 4, 5), strict=True):
        _fact(company, dt.date(year, 1, 1), dt.date(year, 12, 31), value)
    annual = _series(
        "ANNUAL",
        [(dt.date(y, 1, 1), v) for y, v in zip(range(2019, 2024), (2, 4, 5, 4, 5), strict=True)],
        frequency="Annual",
    )
    out = build_macro_overlay(company, annual, concepts=["Revenues"])
    # x = 1..5, y = 2,4,5,4,5: Sxy = 6, Sxx = 10, Syy = 6, r = 6 / sqrt(60).
    assert out["correlation"]["n"] == 5
    assert out["correlation"]["r"] == pytest.approx(0.7745966692, abs=1e-9)


def test_r_is_null_below_three_pairs_and_for_a_constant_side():
    assert pearson([1.0, 2.0], [3.0, 4.0]) is None
    assert pearson([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) is None
    assert pearson([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(-1.0)


def test_annual_only_drops_sub_annual_windows(june_fy):
    _fact(june_fy, dt.date(2023, 7, 1), dt.date(2023, 9, 30), 90)  # a fiscal quarter
    series = _monthly("UNRATE", 60)
    every = build_macro_overlay(june_fy, series, concepts=["Revenues"])
    annual = build_macro_overlay(june_fy, series, concepts=["Revenues"], annual_only=True)
    assert "2023-09-30" in [r["period_end"] for r in every["rows"]]
    assert "2023-09-30" not in [r["period_end"] for r in annual["rows"]]
    assert annual["company_series"]["annual"] is True


def test_derived_metric_takes_its_input_facts_fiscal_window(june_fy):
    for fy, margin in zip((2021, 2022, 2023), ("0.4", "0.5", "0.6"), strict=True):
        DerivedMetric.objects.create(
            company=june_fy, key="gross_margin", period_end=dt.date(fy, 6, 30), value=Decimal(margin)
        )
    series = _monthly("UNRATE", 60)
    out = build_macro_overlay(june_fy, series, metric="gross_margin")

    assert out["company_series"]["source"] == "metric"
    assert [r["period_start"] for r in out["rows"]] == ["2020-07-01", "2021-07-01", "2022-07-01"]
    assert [r["series_value"] for r in out["rows"]] == [11.5, 23.5, 35.5]
    assert out["correlation"]["r"] == pytest.approx(1.0)


def test_instant_values_cover_the_span_since_the_previous_period_end():
    ends = [dt.date(2023, 3, 31), dt.date(2023, 6, 30), dt.date(2023, 9, 30)]
    windows = fiscal_windows([CompanyPoint(period_end=e, value=1.0) for e in ends])
    assert [start for _p, start in windows] == [
        dt.date(2022, 12, 31),  # as many days (91) as the next window, Apr 1 .. Jun 30
        dt.date(2023, 4, 1),
        dt.date(2023, 7, 1),
    ]
    assert fiscal_windows([CompanyPoint(period_end=ends[0], value=1.0)]) == [
        (CompanyPoint(period_end=ends[0], value=1.0), None)
    ]


def test_instant_fact_series_aligns_quarter_by_quarter(company):
    for end, value in (
        (dt.date(2023, 3, 31), 1),
        (dt.date(2023, 6, 30), 2),
        (dt.date(2023, 9, 30), 3),
        (dt.date(2023, 12, 31), 4),
    ):
        Fact.objects.create(
            company=company, concept="Assets", period_end=end, value=Decimal(value), unit="USD"
        )
    series = _monthly("UNRATE", 60)
    out = build_macro_overlay(company, series, concepts=["Assets"], agg="eop")
    assert [r["period_start"] for r in out["rows"]] == [
        "2022-12-31",
        "2023-04-01",
        "2023-07-01",
        "2023-10-01",
    ]
    assert [r["series_value"] for r in out["rows"]] == [38.0, 41.0, 44.0, 47.0]


def test_series_step_is_the_median_spacing():
    assert series_step_days([]) is None
    assert series_step_days([dt.date(2024, 1, 1)]) is None
    assert series_step_days([dt.date(2024, 1, d) for d in (1, 2, 3, 8)]) == 1.0


@responses.activate
def test_find_stored_series_is_db_first_and_case_insensitive(db):
    synced = _monthly("UNRATE", 3)
    ExternalSeries.objects.create(provider="fred", external_id="NEVERSYNCED")
    assert find_stored_series("unrate") == synced
    assert find_stored_series("NEVERSYNCED") is None  # registered but no observations
    assert find_stored_series("NOPE") is None
    assert find_stored_series("  ") is None
    assert len(responses.calls) == 0


def test_bad_arguments_raise_value_error(june_fy):
    series = _monthly("UNRATE", 12)
    with pytest.raises(ValueError, match="agg"):
        build_macro_overlay(june_fy, series, concepts=["Revenues"], agg="median")
    with pytest.raises(ValueError, match="exactly one"):
        build_macro_overlay(june_fy, series)
    with pytest.raises(ValueError, match="exactly one"):
        build_macro_overlay(june_fy, series, metric="gross_margin", concepts=["Revenues"])
    with pytest.raises(ValueError, match="Unknown metric"):
        build_macro_overlay(june_fy, series, metric="not_a_metric")
