"""Static site macro (FRED) section — build-time export, rendering, and graceful absence."""

from __future__ import annotations

import datetime
import decimal
import json

import pytest

from public_data.models import ExternalSeries, SeriesBundle, SeriesBundleItem, SeriesObservation
from public_data.services.static_export import (
    build_macro_context,
    fmt_obs_value,
    macro_data_available,
)
from warehouse.models import Company, Fact
from warehouse.services.static_site import generate_site

FY = {"period_start": datetime.date(2023, 1, 1), "period_end": datetime.date(2023, 12, 31)}


@pytest.fixture
def company(db):
    co = Company.objects.create(cik="0000320193", ticker="AAPL", name="Apple Inc.")
    Fact.objects.create(
        company=co,
        taxonomy="us-gaap",
        concept="Revenues",
        value=decimal.Decimal("383285000000"),
        **FY,
    )
    return co


@pytest.fixture
def macro_bundle(db):
    """A 'rates' bundle with one synced series (monthly observations over 2 years)
    and one never-synced series (must be excluded from the static pages)."""
    bundle = SeriesBundle.objects.create(
        slug="rates", name="Rates & credit", description="Policy rate and the 10Y."
    )
    synced = ExternalSeries.objects.create(
        provider="fred",
        external_id="DGS10",
        title="10-Year Treasury Yield",
        frequency="Daily",
        units="Percent",
        metadata={"note": "The global risk-free benchmark.", "industries": ["Banks", "REITs"]},
    )
    empty = ExternalSeries.objects.create(provider="fred", external_id="NEVERSYNCED")
    SeriesBundleItem.objects.create(bundle=bundle, series=synced, sort_order=0)
    SeriesBundleItem.objects.create(bundle=bundle, series=empty, sort_order=1)

    today = datetime.date.today()
    for months_back in range(24):
        d = today - datetime.timedelta(days=30 * months_back)
        SeriesObservation.objects.create(
            series=synced,
            observation_date=d,
            value=decimal.Decimal("4.0") + decimal.Decimal(months_back) / 100,
        )
    return bundle


def test_fmt_obs_value():
    assert fmt_obs_value(decimal.Decimal("4.20")) == "4.2"
    assert fmt_obs_value(decimal.Decimal("15511.00")) == "15,511"
    assert fmt_obs_value(None) == "—"


@pytest.mark.django_db
def test_macro_context_stats_and_sparkline(macro_bundle):
    assert macro_data_available()
    bundles = build_macro_context()
    assert len(bundles) == 1
    (bundle,) = bundles
    assert bundle["slug"] == "rates"
    # The never-synced series is excluded; the synced one carries real stats.
    assert [s["id"] for s in bundle["series"]] == ["DGS10"]
    s = bundle["series"][0]
    assert s["latest"]["display"] == "4"  # newest observation is 4.0
    assert s["delta_1y"] is not None and s["delta_1y"]["direction"] == "down"
    assert s["spark_points"].count(",") >= 2  # a real polyline, not empty
    assert len(s["table"]) > 0
    assert s["fred_url"] == "https://fred.stlouisfed.org/series/DGS10"


@pytest.mark.django_db
def test_generate_site_renders_macro_section(company, macro_bundle, tmp_path):
    summary = generate_site([company], tmp_path, base_url="https://example.github.io/fredgar-ai")
    assert summary["macro_bundles"] == 1
    assert summary["macro_series"] == 1

    macro_index = (tmp_path / "macro" / "index.html").read_text()
    assert "Rates &amp; credit" in macro_index
    assert "uses the FRED® API" in macro_index  # required FRED attribution

    page = (tmp_path / "macro" / "rates" / "index.html").read_text()
    assert "10-Year Treasury Yield" in page
    assert "https://fred.stlouisfed.org/series/DGS10" in page
    assert "<polyline" in page  # server-rendered sparkline, no JS required
    assert "The global risk-free benchmark." in page
    assert "Banks" in page  # industry-relevance chip

    csv_text = (tmp_path / "macro" / "rates" / "observations.csv").read_text()
    assert csv_text.startswith("series_id,date,value")
    assert csv_text.count("DGS10") == 24  # full synced history, long format

    data = json.loads((tmp_path / "macro" / "rates" / "bundle.json").read_text())
    assert data["slug"] == "rates"
    assert data["series"][0]["latest"]["value"]

    # Nav link + landing card + sitemap all point at the macro section.
    index_html = (tmp_path / "index.html").read_text()
    assert 'href="macro/index.html"' in index_html
    assert "Browse macro data" in index_html
    sitemap = (tmp_path / "sitemap.xml").read_text()
    assert "https://example.github.io/fredgar-ai/macro/index.html" in sitemap
    assert "https://example.github.io/fredgar-ai/macro/rates/index.html" in sitemap

    # Company pages resolve the nav link via their ../../ prefix.
    company_page = (tmp_path / "companies" / company.cik / "index.html").read_text()
    assert '"../../macro/index.html"' in company_page


@pytest.mark.django_db
def test_generate_site_omits_macro_section_without_data(company, tmp_path):
    """No synced series -> no macro dir, no nav link, no empty shell pages."""
    assert not macro_data_available()
    summary = generate_site([company], tmp_path, base_url="https://example.github.io/fredgar-ai")
    assert summary["macro_bundles"] == 0
    assert not (tmp_path / "macro").exists()
    index_html = (tmp_path / "index.html").read_text()
    assert 'href="macro/index.html"' not in index_html
    assert "macro/index.html" not in (tmp_path / "sitemap.xml").read_text()


@pytest.mark.django_db
def test_publish_site_skips_macro_sync_without_api_key(company, tmp_path, monkeypatch):
    """No FRED_API_KEY -> macro sync silently skipped, publish still succeeds."""
    from warehouse.services import static_site_publish

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    summary = static_site_publish.publish_site(["AAPL"], tmp_path, sync=False)
    assert summary["macro_synced"] is False
    assert (tmp_path / "index.html").exists()


@pytest.mark.django_db
def test_publish_site_macro_sync_failure_never_blocks_publish(company, tmp_path, monkeypatch):
    """A blowing-up FRED sync is contained; companies still publish."""
    from warehouse.services import static_site_publish

    def boom(**kwargs):
        raise RuntimeError("FRED down")

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    monkeypatch.setattr(static_site_publish, "sync_company_for_site", lambda t, **kw: company)
    import django.core.management as mgmt

    monkeypatch.setattr(mgmt, "call_command", boom)
    summary = static_site_publish.publish_site(["AAPL"], tmp_path, delay=0)
    assert summary["macro_synced"] is False
    assert (tmp_path / "index.html").exists()
