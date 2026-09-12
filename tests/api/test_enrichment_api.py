"""The enrichment API: resolved values, the evidence behind them, the review queue."""

import pytest
from django.utils import timezone

from warehouse.models import (
    Company,
    EnrichmentClaim,
    EnrichmentDataset,
    EnrichmentGoldenField,
    EnrichmentRecord,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def enriched():
    dataset = EnrichmentDataset.objects.create(slug="vendors", name="Vendor list")
    company = Company.objects.create(cik="0001551182", ticker="ETN", name="Eaton Corp plc")
    record = EnrichmentRecord.objects.create(
        dataset=dataset,
        source_key="Eaton Corporation plc HQ",
        seed={"name": "Eaton Corporation plc HQ"},
        company=company,
    )
    EnrichmentClaim.objects.create(
        record=record,
        field="revenue_reported",
        value=27_448_000_000.0,
        value_hash="a" * 40,
        confidence=0.97,
        provider="edgar_facts",
        verified=True,
        ev_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0001551182.json",
        ev_locator="xbrl:us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax:CY2025",
        retrieved_at=timezone.now(),
    )
    EnrichmentGoldenField.objects.create(
        record=record,
        field="revenue_reported",
        value=27_448_000_000.0,
        confidence=0.97,
        provider="edgar_facts",
        ev_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0001551182.json",
    )
    EnrichmentGoldenField.objects.create(
        record=record,
        field="hq_city",
        value="Dublin",
        confidence=0.93,
        provider="edgar_submissions",
        rivals=1,
        contested=True,
    )
    return dataset, record


def test_datasets_list_with_record_counts(api_client, enriched):
    response = api_client.get("/api/v1/enrichment-datasets/")
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert row["slug"] == "vendors"
    assert row["records"] == 1


def test_dataset_report_exposes_coverage_and_validation_tiers(api_client, enriched):
    response = api_client.get("/api/v1/enrichment-datasets/vendors/report/")
    assert response.status_code == 200
    body = response.json()
    assert body["records"] == 1
    assert body["coverage"]["revenue_reported"] == 1
    assert body["contested_fields"] == 1
    assert "validation_status" in body


def test_record_detail_carries_resolved_values(api_client, enriched):
    _, record = enriched
    response = api_client.get(f"/api/v1/enrichment-records/{record.pk}/")
    assert response.status_code == 200
    body = response.json()
    assert body["dataset"] == "vendors"
    fields = {g["field"]: g for g in body["golden"]}
    assert fields["revenue_reported"]["value"] == 27_448_000_000.0
    assert fields["hq_city"]["contested"] is True


def test_evidence_answers_why_does_it_say_that(api_client, enriched):
    """The endpoint the whole claim model exists to make possible."""
    _, record = enriched
    response = api_client.get(f"/api/v1/enrichment-records/{record.pk}/evidence/")
    assert response.status_code == 200
    body = response.json()

    claim = body["claims"][0]
    assert claim["provider"] == "edgar_facts"
    assert claim["verified"] is True
    assert claim["ev_url"].startswith("https://data.sec.gov/")
    assert claim["ev_locator"].startswith("xbrl:")


def test_contested_is_a_review_queue(api_client, enriched):
    response = api_client.get("/api/v1/enrichment-records/contested/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


def test_records_filter_by_dataset(api_client, enriched):
    EnrichmentDataset.objects.create(slug="other", name="Other list")
    response = api_client.get("/api/v1/enrichment-records/?dataset__slug=other")
    assert response.json()["results"] == []


def test_enrichment_is_read_only_over_http(admin_client, enriched):
    """Running providers spends SEC budget and takes minutes; it is not a request."""
    response = admin_client.post("/api/v1/enrichment-records/", {"source_key": "x"}, format="json")
    assert response.status_code == 405
