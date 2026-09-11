"""FRED macro context and the EDGAR-to-FRED deflator join."""

import datetime as dt

import pytest
from django.utils import timezone

from enrichment.core.model import Record
from enrichment.core.runner import Context
from enrichment.providers.fred import (
    FredDeflator,
    FredMacroContext,
    bundle_for_sic,
    bundles_for,
    load_bundles,
)
from public_data.models import ExternalSeries, SeriesObservation

pytestmark = pytest.mark.django_db


def make_record(**fields) -> Record:
    seed = {"name": "Test Manufacturing Ltd"}
    seed.update(fields)
    return Record(1, seed["name"], seed)


def run(provider, rec):
    return list(provider.run(rec, Context()))


def test_committed_bundles_load():
    bundles = load_bundles()
    assert "manufacturing" in bundles
    assert bundles["manufacturing"]["series"][0]["id"] == "IPMAN"


def test_sic_classifies_better_than_end_market_tags():
    """SEC's SIC says what a filer makes; a supplier list's verticals say who buys it.

    Eaton is tagged "Automotive|Consumer Products|Electronics|Industrial|Life
    Sciences" — five end markets, alphabetically — so the vertical tags alone
    routed it to the autos bundle. SIC 3590 is industrial machinery.
    """
    assert bundle_for_sic("3590") == "manufacturing"
    assert bundle_for_sic("3711") == "autos"
    assert bundle_for_sic("2834") == "healthcare"  # drugs, via the 3-digit prefix
    assert bundle_for_sic("2810") == "materials"  # other chemicals, via 2-digit
    assert bundle_for_sic(None) is None

    verticals = ["Automotive", "Consumer Products", "Industrial"]
    assert bundles_for(verticals, sic="3590")[0] == "manufacturing"
    assert bundles_for(verticals)[0] == "autos"  # without SIC, the tags decide


def test_goods_economy_is_the_floor_not_silence():
    assert bundles_for([]) == ["manufacturing"]


def test_us_records_are_domestic_and_others_are_labelled_a_proxy():
    """FRED measures the United States. Applying it elsewhere must say so."""
    domestic = run(FredMacroContext(), make_record(geo_iso2="US", sic="3590"))
    scope = next(c for c in domestic if c.field == "macro_scope")
    assert scope.value == "domestic_us"

    foreign = run(FredMacroContext(), make_record(geo_iso2="MY", sic="3590"))
    scope = next(c for c in foreign if c.field == "macro_scope")
    assert scope.value == "us_proxy"

    series = next(c for c in foreign if c.field == "macro_series")
    assert series.confidence < 0.5
    assert "proxy" in series.evidence.snippet


def test_macro_series_carry_a_citable_fred_url():
    claims = run(FredMacroContext(), make_record(geo_iso2="US", sic="3590"))
    series = [c for c in claims if c.field == "macro_series"]
    assert series
    for claim in series:
        assert claim.value["url"].startswith("https://fred.stlouisfed.org/series/")
        assert claim.evidence.url == claim.value["url"]


def test_latest_observation_is_attached_when_the_series_is_synced():
    series = ExternalSeries.objects.create(provider="fred", external_id="IPMAN", units="Index")
    SeriesObservation.objects.create(
        series=series, observation_date=dt.date(2026, 8, 1), value="104.5"
    )
    claims = run(FredMacroContext(), make_record(geo_iso2="US", sic="3590"))
    ipman = next(c for c in claims if c.field == "macro_series" and c.value["id"] == "IPMAN")
    assert ipman.value["latest_value"] == 104.5
    assert ipman.value["latest_date"] == "2026-08-01"


def test_unsynced_series_have_no_observation_rather_than_a_guess():
    claims = run(FredMacroContext(), make_record(geo_iso2="US", sic="3590"))
    ipman = next(c for c in claims if c.field == "macro_series" and c.value["id"] == "IPMAN")
    assert ipman.value["latest_value"] is None


# ------------------------------------------------------------------ deflator --


def test_deflator_restates_a_reported_revenue_in_current_dollars():
    """The EDGAR-to-FRED join: a filed FY number, priced at today's index."""
    series = ExternalSeries.objects.create(provider="fred", external_id="PCUOMFGOMFG")
    SeriesObservation.objects.create(
        series=series, observation_date=dt.date(2019, 12, 1), value="100.0"
    )
    SeriesObservation.objects.create(
        series=series, observation_date=dt.date(2026, 6, 1), value="125.0"
    )

    rec = make_record(
        revenue_reported=1_000_000.0,
        revenue_period_end="2019-12-31",
        macro_bundle=["manufacturing"],
    )
    claims = {c.field: c for c in run(FredDeflator(), rec)}

    assert claims["revenue_real"].value == pytest.approx(1_250_000.0)
    assert claims["revenue_deflator"].value == pytest.approx(1.25)
    assert claims["revenue_deflator_series"].value == "PCUOMFGOMFG"
    assert claims["revenue_real_base"].value == "2026-06-01"
    assert "PCUOMFGOMFG" in claims["revenue_real"].evidence.url


def test_deflator_is_silent_without_the_index_rather_than_approximating():
    """A deflator guessed from a neighbouring series is a rounding error with a URL."""
    rec = make_record(revenue_reported=1_000_000.0, revenue_period_end="2019-12-31")
    assert run(FredDeflator(), rec) == []


def test_deflator_needs_an_observation_at_or_before_the_fiscal_period():
    """An index that only starts after the filing cannot price it."""
    series = ExternalSeries.objects.create(provider="fred", external_id="CPIAUCSL")
    SeriesObservation.objects.create(
        series=series, observation_date=dt.date(2026, 6, 1), value="125.0"
    )
    rec = make_record(revenue_reported=1_000_000.0, revenue_period_end="2019-12-31")
    assert run(FredDeflator(), rec) == []


def test_sector_deflator_is_preferred_over_headline_cpi():
    for name in ("PCUOMFGOMFG", "CPIAUCSL"):
        series = ExternalSeries.objects.create(provider="fred", external_id=name)
        SeriesObservation.objects.create(
            series=series, observation_date=dt.date(2019, 12, 1), value="100.0"
        )
        SeriesObservation.objects.create(
            series=series, observation_date=dt.date(2026, 6, 1), value="110.0"
        )

    rec = make_record(
        revenue_reported=1.0, revenue_period_end="2019-12-31", macro_bundle=["manufacturing"]
    )
    claims = {c.field: c.value for c in run(FredDeflator(), rec)}
    assert claims["revenue_deflator_series"] == "PCUOMFGOMFG"

    generic = make_record(
        revenue_reported=1.0, revenue_period_end="2019-12-31", macro_bundle=["financials"]
    )
    claims = {c.field: c.value for c in run(FredDeflator(), generic)}
    assert claims["revenue_deflator_series"] == "CPIAUCSL"


def test_deflator_never_touches_the_network(monkeypatch):
    """Everything here reads the warehouse; FRED_API_KEY is irrelevant to it."""
    import requests

    def explode(*args, **kwargs):  # pragma: no cover - fails the test if reached
        raise AssertionError("FredDeflator must not make HTTP requests")

    monkeypatch.setattr(requests, "get", explode)
    rec = make_record(revenue_reported=1.0, revenue_period_end="2019-12-31")
    assert run(FredDeflator(), rec) == []
    assert timezone.now() is not None
