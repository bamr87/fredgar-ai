"""Static site generation (the 'Wikipedia of company financials')."""

from __future__ import annotations

import datetime
import decimal
import json

import pytest
from django.core.management import call_command

from warehouse.models import (
    Company,
    DerivedMetric,
    Fact,
    Filing,
    FilingDocument,
    LeadershipPosition,
    Person,
)
from warehouse.services.static_site import (
    FEATURED_LIMIT,
    build_company_context,
    fmt_value,
    generate_site,
)

FY = {"period_start": datetime.date(2023, 1, 1), "period_end": datetime.date(2023, 12, 31)}


@pytest.fixture
def company(db):
    co = Company.objects.create(
        cik="0000320193",
        ticker="AAPL",
        name="Apple Inc.",
        sic_code="3571",
        sic_description="Electronic Computers",
        hq_state="CA",
    )
    Fact.objects.create(
        company=co,
        taxonomy="us-gaap",
        concept="Revenues",
        value=decimal.Decimal("383285000000"),
        dimensions={"accn": "0000320193-23-000106"},
        **FY,
    )
    Fact.objects.create(
        company=co,
        taxonomy="us-gaap",
        concept="CostOfGoodsAndServicesSold",
        value=decimal.Decimal("214137000000"),
        **FY,
    )
    Fact.objects.create(
        company=co,
        taxonomy="us-gaap",
        concept="NetIncomeLoss",
        value=decimal.Decimal("96995000000"),
        **FY,
    )
    DerivedMetric.objects.create(
        company=co,
        key="gross_margin",
        period_end=FY["period_end"],
        value=decimal.Decimal("0.441"),
        unit="ratio",
    )
    f = Filing.objects.create(
        company=co,
        accession_number="0000320193-23-000106",
        form_type="10-K",
        filing_date=FY["period_end"],
    )
    FilingDocument.objects.create(
        filing=f,
        sequence=1,
        sha1="x",
        type="10-K",
        file_name="aapl.htm",
        content_type="text/html",
        text="Apple annual report discussion.",
    )
    return co


def test_fmt_value():
    assert fmt_value(383285000000, "USD") == "383,285,000,000"
    assert fmt_value(decimal.Decimal("0.441"), "ratio") == "0.4410"
    assert fmt_value(None, "USD") == "—"


@pytest.mark.django_db
def test_build_company_context(company):
    ctx = build_company_context(company)
    assert ctx["company"]["ticker"] == "AAPL"
    assert ctx["company"]["hq"] == "CA, US"
    assert ctx["counts"]["facts"] == 3
    assert any(h["label"] == "Revenue" for h in ctx["headline"])
    assert any(m["key"] == "gross_margin" for m in ctx["metrics"])
    income = next(s for s in ctx["statements"] if s["type"] == "income_statement")
    assert any(r["label"] == "Revenue" and r["value"] == 383285000000.0 for r in income["rows"])
    # statement line links to the source filing
    assert any(r["accession"] == "0000320193-23-000106" for r in income["rows"])


@pytest.fixture
def thin_company(db):
    """A company with facts but no HEADLINE_CONCEPTS present (tests graceful fallback)."""
    co = Company.objects.create(cik="0000000001", ticker="THIN", name="Thin Data Co")
    Fact.objects.create(
        company=co,
        taxonomy="us-gaap",
        concept="SomeOtherConcept",
        value=decimal.Decimal("1"),
        **FY,
    )
    Filing.objects.create(
        company=co,
        accession_number="0000000001-23-000001",
        form_type="10-K",
        filing_date=FY["period_end"],
    )
    return co


@pytest.mark.django_db
def test_generate_site_files(company, tmp_path):
    summary = generate_site([company], tmp_path)
    assert summary["pages"] == 1

    index_html = (tmp_path / "index.html").read_text()
    assert "Apple Inc." in index_html
    assert "companies.csv" in index_html  # site-wide download link

    cdir = tmp_path / "companies" / company.cik
    page = (cdir / "index.html").read_text()
    assert "Apple Inc." in page
    assert "Income Statement" in page
    assert "gross_margin" in page
    assert 'href="facts.csv"' in page  # download affordance
    assert "copyTable(" in page  # copy affordance
    assert "383,285,000,000" in page  # formatted headline value

    data = json.loads((cdir / "company.json").read_text())
    assert data["company"]["cik"] == company.cik
    assert data["counts"]["facts"] == 3

    facts_csv = (cdir / "facts.csv").read_text()
    assert facts_csv.startswith("concept,taxonomy,")
    assert "Revenues" in facts_csv

    metrics_csv = (cdir / "metrics.csv").read_text()
    assert "gross_margin" in metrics_csv
    assert (cdir / "statements.csv").exists()
    assert (cdir / "filings.csv").exists()

    assert (tmp_path / "companies.json").exists()
    assert (tmp_path / "companies.csv").read_text().startswith("cik,ticker,name,")


@pytest.mark.django_db
def test_generate_static_site_command(company, tmp_path):
    call_command("generate_static_site", "--ticker", "AAPL", "--output", str(tmp_path))
    assert (tmp_path / "companies" / company.cik / "index.html").exists()
    assert (tmp_path / "index.html").exists()


@pytest.mark.django_db
def test_generate_site_publishing_extras(company, tmp_path):
    """GitHub Pages needs .nojekyll; base_url enables sitemap/robots; app_url cross-links."""
    generate_site(
        [company],
        tmp_path,
        base_url="https://example.github.io/fredgar-ai",
        app_url="https://app.example.com",
    )
    assert (tmp_path / ".nojekyll").exists()

    about = (tmp_path / "about.html").read_text()
    assert "static mirror" in about
    assert "https://app.example.com/" in about  # cross-link to the interactive app

    sitemap = (tmp_path / "sitemap.xml").read_text()
    assert f"https://example.github.io/fredgar-ai/companies/{company.cik}/index.html" in sitemap
    assert "about.html" in sitemap
    robots = (tmp_path / "robots.txt").read_text()
    assert "Sitemap: https://example.github.io/fredgar-ai/sitemap.xml" in robots

    # Company pages resolve site-root links via the ../../ prefix.
    page = (tmp_path / "companies" / company.cik / "index.html").read_text()
    assert "../../about.html" in page


@pytest.mark.django_db
def test_generate_site_without_base_url_skips_seo_files(company, tmp_path):
    generate_site([company], tmp_path, base_url="", app_url="", source_url="")
    assert (tmp_path / ".nojekyll").exists()
    assert not (tmp_path / "sitemap.xml").exists()
    assert not (tmp_path / "robots.txt").exists()


@pytest.mark.django_db
def test_publish_static_site_command_skip_sync(company, tmp_path):
    """--skip-sync renders from warehouse data with no SEC calls; unknown tickers are reported."""
    call_command(
        "publish_static_site",
        "--skip-sync",
        "--tickers",
        "AAPL,ZZZZ",
        "--output",
        str(tmp_path),
        "--base-url",
        "https://example.github.io/fredgar-ai",
    )
    assert (tmp_path / "companies" / company.cik / "index.html").exists()
    assert (tmp_path / "about.html").exists()
    assert (tmp_path / "sitemap.xml").exists()


@pytest.mark.django_db
def test_publish_static_site_command_fails_when_nothing_publishable(tmp_path):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command(
            "publish_static_site",
            "--skip-sync",
            "--tickers",
            "ZZZZ",
            "--output",
            str(tmp_path),
        )


@pytest.mark.django_db
def test_publish_site_tolerates_per_ticker_sync_failures(company, tmp_path, monkeypatch):
    """One ticker failing to sync must not abort the publish of the others."""
    from warehouse.services import static_site_publish

    def fake_sync(ticker, **kwargs):
        if ticker == "FAIL":
            raise RuntimeError("SEC unavailable")
        return company

    monkeypatch.setattr(static_site_publish, "sync_company_for_site", fake_sync)
    summary = static_site_publish.publish_site(["FAIL", "AAPL"], tmp_path, delay=0)
    assert summary["companies"] == 1
    assert "SEC unavailable" in summary["errors"]["FAIL"]
    assert (tmp_path / "companies" / company.cik / "index.html").exists()


@pytest.mark.django_db
def test_landing_page_hero_and_stats(company, tmp_path):
    """index.html is a landing/hero page: real aggregate stats, not the raw company table alone."""
    generate_site([company], tmp_path)
    index_html = (tmp_path / "index.html").read_text()

    # Hero content present, and it's the same document as the (relocated) browse table.
    assert "Every number here traces back to a real SEC filing." in index_html
    assert 'id="browse"' in index_html
    assert "companies.csv" in index_html

    # Aggregate stats are real sums over the published companies, rendered as the
    # JS count-up target (data-count) AND as the no-JS fallback text content.
    assert 'data-count="1"' in index_html  # company_count
    assert 'data-count="3"' in index_html  # total_facts (3 facts on the fixture company)
    assert 'data-count="1"' in index_html  # total_filings


@pytest.mark.django_db
def test_landing_page_demo_widget_shows_real_headline_data(company, tmp_path):
    """The live JS demo widget must be built from real, already-computed headline data."""
    generate_site([company], tmp_path)
    index_html = (tmp_path / "index.html").read_text()

    assert 'id="demo-pills"' in index_html
    assert 'id="demo-cards"' in index_html
    assert "AAPL" in index_html  # pill label
    assert "383,285,000,000" in index_html  # real formatted Revenue figure, not a placeholder
    assert "XBRL facts" in index_html and "filings behind this page" in index_html
    assert f"companies/{company.cik}/index.html" in index_html  # "View full profile" link
    # Progressive enhancement: cards are unconditionally rendered (visible without JS);
    # JS only toggles which one is active.
    assert index_html.count('class="example-card') == 1


@pytest.mark.django_db
def test_landing_page_demo_widget_handles_company_without_headline_data(
    company, thin_company, tmp_path
):
    """A company with facts but none of the HEADLINE_CONCEPTS must not crash the build and
    must render a graceful fallback instead of empty/blank figures."""
    generate_site([company, thin_company], tmp_path)
    index_html = (tmp_path / "index.html").read_text()

    assert "Thin Data Co" in index_html
    assert "Financial snapshot not yet computed for this company." in index_html
    assert 'data-count="2"' in index_html  # company_count now 2


@pytest.mark.django_db
def test_landing_page_featured_prefers_richer_companies_and_caps_at_limit(db, tmp_path):
    """Featured selection should prefer companies with headline data and never exceed FEATURED_LIMIT."""
    companies = []
    for i in range(FEATURED_LIMIT + 3):
        co = Company.objects.create(cik=f"{i:010d}", ticker=f"T{i}", name=f"Company {i}")
        Fact.objects.create(
            company=co,
            taxonomy="us-gaap",
            concept="Revenues",
            value=decimal.Decimal(1000 + i),
            **FY,
        )
        companies.append(co)

    generate_site(companies, tmp_path)
    index_html = (tmp_path / "index.html").read_text()
    assert index_html.count('class="example-card') <= FEATURED_LIMIT


@pytest.mark.django_db
def test_landing_page_feature_tour_links_respect_app_url(company, tmp_path):
    """App-only capabilities must only link out when an interactive-app URL is configured."""
    generate_site([company], tmp_path / "no-app")
    no_app_html = (tmp_path / "no-app" / "index.html").read_text()
    assert "Compare &amp; peer groups" in no_app_html
    assert 'href="https://app.example.com/compare"' not in no_app_html

    generate_site([company], tmp_path / "with-app", app_url="https://app.example.com")
    with_app_html = (tmp_path / "with-app" / "index.html").read_text()
    assert 'href="https://app.example.com/compare"' in with_app_html


@pytest.mark.django_db
def test_landing_deep_links_only_target_existing_anchors(company, tmp_path):
    """Feature-tour deep links must not point at company-page sections that don't exist.

    The publish pipeline never ingests FilingDocuments, so the mirror has no
    ``#documents`` section; and leadership is best-effort, so ``#leadership`` is
    only linked when the exemplar company actually has leadership data.
    """
    # The `company` fixture has facts/statements/metrics but no LeadershipPosition
    # and no ingested documents.
    generate_site([company], tmp_path)
    index_html = (tmp_path / "index.html").read_text()

    # The dropped "Filing documents" card must be gone entirely (no dangling anchor).
    assert "#documents" not in index_html
    # Always-present sections are safe to deep-link.
    assert f"companies/{company.cik}/index.html#statements" in index_html
    assert f"companies/{company.cik}/index.html#metrics" in index_html
    assert f"companies/{company.cik}/index.html#facts" in index_html
    # No leadership data -> the leadership card links to the page (no #leadership fragment).
    assert f'href="companies/{company.cik}/index.html#leadership"' not in index_html


@pytest.mark.django_db
def test_landing_leadership_deep_link_appears_when_data_exists(tmp_path):
    """When the featured company has leadership data, the #leadership anchor is linked."""
    co = Company.objects.create(cik="0000000042", ticker="LEAD", name="Leader Co")
    Fact.objects.create(
        company=co,
        taxonomy="us-gaap",
        concept="Revenues",
        value=decimal.Decimal("100"),
        **FY,
    )
    person = Person.objects.create(full_name="Jane Executive")
    LeadershipPosition.objects.create(
        company=co,
        person=person,
        title="Chief Executive Officer",
        is_officer=True,
        is_director=True,
        first_seen=FY["period_end"],
        last_seen=FY["period_end"],
        filings_count=3,
        net_insider_shares=decimal.Decimal("0"),
    )

    generate_site([co], tmp_path)
    index_html = (tmp_path / "index.html").read_text()
    assert f'href="companies/{co.cik}/index.html#leadership"' in index_html


@pytest.mark.django_db
def test_landing_demo_widget_has_empty_state(company, tmp_path):
    """The demo search box needs a 'no matches' element (parity with the browse table)."""
    generate_site([company], tmp_path)
    index_html = (tmp_path / "index.html").read_text()
    assert 'id="demo-empty"' in index_html
