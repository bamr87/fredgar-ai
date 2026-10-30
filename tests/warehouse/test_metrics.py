"""DerivedMetric computation from Facts (Phase 5)."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from warehouse.models import Company, DerivedMetric, Fact
from warehouse.services.edgar.metrics import compute_derived_metrics

FY = {"period_start": datetime.date(2023, 1, 1), "period_end": datetime.date(2023, 12, 31)}


def _fact(company, concept, value, **kw):
    base = {"taxonomy": "us-gaap", "value": Decimal(value), **FY}
    base.update(kw)
    return Fact.objects.create(company=company, concept=concept, **base)


@pytest.mark.django_db
def test_gross_margin_computed():
    co = Company.objects.create(cik="0000320193", ticker="AAPL", name="Apple")
    _fact(co, "Revenues", "100", dimensions={"accn": "0000320193-24-000001"})
    _fact(co, "CostOfGoodsAndServicesSold", "60")

    written = compute_derived_metrics(co)
    assert written >= 1

    gm = DerivedMetric.objects.get(company=co, key="gross_margin", period_end=FY["period_end"])
    # (100 - 60) / 100 = 0.4
    assert gm.value == Decimal("0.400000")
    assert gm.unit == "ratio"
    assert gm.extra["source"] == "computed:financial_model"
    assert "fetched_at" in gm.extra


@pytest.mark.django_db
def test_zero_revenue_skips_gross_margin():
    co = Company.objects.create(cik="0000000001", name="ZeroCo")
    _fact(co, "Revenues", "0")
    _fact(co, "CostOfGoodsAndServicesSold", "10")

    compute_derived_metrics(co)
    assert not DerivedMetric.objects.filter(company=co, key="gross_margin").exists()


@pytest.mark.django_db
def test_missing_operand_skips_metric():
    co = Company.objects.create(cik="0000000002", name="NoCostCo")
    _fact(co, "Revenues", "100")  # no cost_of_revenue fact

    compute_derived_metrics(co)
    # gross_margin requires both revenue and cost_of_revenue
    assert not DerivedMetric.objects.filter(company=co, key="gross_margin").exists()


@pytest.mark.django_db
def test_concept_preference_order():
    """The first concept in a group's preference list wins."""
    co = Company.objects.create(cik="0000000003", name="PrefCo")
    # "Revenues" is preferred over "SalesRevenueNet" in the revenue group.
    _fact(co, "Revenues", "200")
    _fact(co, "SalesRevenueNet", "999")
    _fact(co, "CostOfGoodsAndServicesSold", "100")

    compute_derived_metrics(co)
    gm = DerivedMetric.objects.get(company=co, key="gross_margin")
    # (200 - 100) / 200 = 0.5  (uses Revenues=200, not SalesRevenueNet)
    assert gm.value == Decimal("0.500000")


@pytest.mark.django_db
def test_recompute_is_idempotent():
    co = Company.objects.create(cik="0000000004", name="IdemCo")
    _fact(co, "Revenues", "100")
    _fact(co, "CostOfGoodsAndServicesSold", "40")

    compute_derived_metrics(co)
    first = DerivedMetric.objects.filter(company=co).count()
    compute_derived_metrics(co)
    assert DerivedMetric.objects.filter(company=co).count() == first


@pytest.mark.django_db
def test_cheat_sheet_kpis_computed_from_facts():
    """ROE, ROA, D/E, current, quick, EPS, EBITDA and interest coverage from XBRL facts."""
    co = Company.objects.create(cik="0000000099", name="RatioCo")
    fy_end = FY["period_end"]
    instant = {"period_start": None, "period_end": fy_end}
    _fact(co, "NetIncomeLoss", "150")
    _fact(co, "WeightedAverageNumberOfSharesOutstandingBasic", "50", unit="shares")
    _fact(co, "InterestExpense", "20")
    _fact(co, "IncomeTaxExpenseBenefit", "30")
    _fact(co, "DepreciationDepletionAndAmortization", "50")
    _fact(co, "OperatingIncomeLoss", "200")
    _fact(co, "StockholdersEquity", "1000", **instant)
    _fact(co, "Assets", "3000", **instant)
    _fact(co, "LongTermDebt", "500", **instant)
    _fact(co, "AssetsCurrent", "300", **instant)
    _fact(co, "InventoryNet", "60", **instant)
    _fact(co, "LiabilitiesCurrent", "150", **instant)

    compute_derived_metrics(co)
    got = {m.key: m for m in DerivedMetric.objects.filter(company=co, period_end=fy_end)}
    assert got["return_on_equity"].value == Decimal("0.150000")  # 150 / 1000
    assert got["return_on_assets"].value == Decimal("0.050000")  # 150 / 3000
    assert got["debt_to_equity"].value == Decimal("0.500000")  # 500 / 1000
    assert got["current_ratio"].value == Decimal("2.000000")  # 300 / 150
    assert got["quick_ratio"].value == Decimal("1.600000")  # (300 - 60) / 150
    assert got["eps_basic_computed"].value == Decimal("3.000000")  # 150 / 50
    assert got["interest_coverage"].value == Decimal("10.000000")  # 200 / 20
    assert got["ebitda"].value == Decimal("250.000000")  # 150 + 20 + 30 + 50
    assert got["ebitda"].unit == "USD"
    assert got["return_on_equity"].unit == "ratio"
