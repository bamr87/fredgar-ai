"""GET /api/v1/companies/{id}/macro-overlay/ — DB-first, validated, never calls FRED or SEC."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
import responses

from public_data.models import ExternalSeries, SeriesObservation
from warehouse.models import Company, Fact


@pytest.fixture
def company(db):
    co = Company.objects.create(cik="0000000113", ticker="OVLY", name="Overlay Corp")
    for year, revenue in zip(range(2019, 2024), (10, 12, 11, 15, 16), strict=True):
        Fact.objects.create(
            company=co,
            concept="Revenues",
            period_start=dt.date(year, 1, 1),
            period_end=dt.date(year, 12, 31),
            value=Decimal(revenue),
            unit="USD",
        )
    return co


@pytest.fixture
def gdp(db):
    s = ExternalSeries.objects.create(
        provider="fred", external_id="GDP", title="Gross Domestic Product", frequency="Quarterly"
    )
    quarters = [dt.date(2018 + q // 4, (q % 4) * 3 + 1, 1) for q in range(28)]  # 2018Q1 .. 2024Q4
    SeriesObservation.objects.bulk_create(
        [
            SeriesObservation(series=s, observation_date=d, value=Decimal(20000 + 100 * i))
            for i, d in enumerate(quarters)
        ]
    )
    return s


def _url(company_id: int) -> str:
    return f"/api/v1/companies/{company_id}/macro-overlay/"


@responses.activate
def test_overlay_returns_aligned_rows_correlation_and_alignment(api_client, company, gdp):
    resp = api_client.get(_url(company.id), {"concept": "Revenues", "series": "GDP"})
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["series"]["external_id"] == "GDP"
    assert body["company_series"] == {
        "source": "concept",
        "key": "Revenues",
        "concepts": ["Revenues"],
        "taxonomy": "us-gaap",
        "unit": "USD",
        "annual": False,
    }
    assert [r["period_end"] for r in body["rows"]] == [f"{y}-12-31" for y in range(2019, 2024)]
    # 2019 = quarters 4..7 of the fixture: mean of 20400..20700.
    assert body["rows"][0]["series_value"] == 20550.0
    assert body["rows"][0]["series_observations"] == 4
    assert set(body["correlation"]) == {"method", "r", "n"}
    assert body["correlation"]["n"] == 5
    assert -1.0 <= body["correlation"]["r"] <= 1.0
    assert body["alignment"]["aggregation"] == "avg"
    assert body["alignment"]["description"]
    assert len(responses.calls) == 0  # DB-first: no SEC or FRED call


@responses.activate
def test_overlay_accepts_a_concept_chain_eop_and_annual(api_client, company, gdp):
    resp = api_client.get(
        _url(company.id),
        {"concept": "RevenueFromContractWithCustomerExcludingAssessedTax,Revenues", "series": "gdp", "agg": "EOP", "annual": "1"},
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["company_series"]["concepts"][1] == "Revenues"
    assert body["company_series"]["annual"] is True
    assert body["alignment"]["aggregation"] == "eop"
    assert body["rows"][0]["series_value"] == 20700.0  # 2019Q4
    assert len(responses.calls) == 0


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"series": "GDP"}, "exactly one of metric"),
        ({"metric": "gross_margin", "concept": "Revenues", "series": "GDP"}, "exactly one of metric"),
        ({"metric": "not_a_metric", "series": "GDP"}, "Unknown metric"),
        ({"concept": "Revenues"}, "series query parameter"),
        ({"concept": "Revenues", "series": "GDP", "agg": "median"}, "Unknown agg"),
    ],
)
@responses.activate
def test_overlay_rejects_missing_or_unknown_parameters(api_client, company, gdp, params, detail):
    resp = api_client.get(_url(company.id), params)
    assert resp.status_code == 400
    assert detail in resp.json()["detail"]
    assert len(responses.calls) == 0


@responses.activate
def test_unknown_metric_lists_the_known_ones(api_client, company, gdp):
    resp = api_client.get(_url(company.id), {"metric": "nope", "series": "GDP"})
    assert resp.status_code == 400
    assert "gross_margin" in resp.json()["metrics"]


@pytest.mark.parametrize("series_id", ["NOPE", "NEVERSYNCED"])
@responses.activate
def test_series_not_stored_is_404_without_calling_fred(api_client, company, series_id):
    ExternalSeries.objects.create(provider="fred", external_id="NEVERSYNCED")
    resp = api_client.get(_url(company.id), {"concept": "Revenues", "series": series_id})
    assert resp.status_code == 404
    assert "never calls FRED" in resp.json()["detail"]
    assert len(responses.calls) == 0


def test_unknown_company_is_404(api_client, gdp):
    resp = api_client.get(_url(999999), {"concept": "Revenues", "series": "GDP"})
    assert resp.status_code == 404
