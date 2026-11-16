"""The ``cik`` filter on ``GET /api/v1/filings/search/`` (issue #126).

A malformed ``cik`` used to be dropped without a word, so a caller who meant to
search one company silently got every company's documents. It is now a 400; a
valid ``cik`` narrows the search and a missing or empty one searches everything.
"""

from __future__ import annotations

import pytest
from rest_framework import status

from warehouse.models import Company, Filing, FilingDocument

URL = "/api/v1/filings/search/"
APPLE_CIK = "0000320193"
MSFT_CIK = "0000789019"


def _document(cik: str, ticker: str, accession: str) -> FilingDocument:
    company = Company.objects.create(cik=cik, ticker=ticker, name=ticker)
    filing = Filing.objects.create(company=company, accession_number=accession, form_type="10-K")
    return FilingDocument.objects.create(
        filing=filing,
        sequence=1,
        type="10-K",
        file_name=f"{ticker.lower()}-10k.htm",
        sha1="0" * 40,
        text=f"{ticker} annual report discussing revenue growth.",
        is_processed=True,
    )


@pytest.fixture
def two_companies(db) -> None:
    _document(APPLE_CIK, "AAPL", "0000320193-24-000123")
    _document(MSFT_CIK, "MSFT", "0000789019-24-000456")


@pytest.mark.parametrize("cik", ["abc", "CIK", "12345678901"])
def test_invalid_cik_is_rejected(api_client, two_companies, cik: str) -> None:
    r = api_client.get(URL, {"q": "revenue", "cik": cik})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "cik" in r.json()["detail"].lower()


@pytest.mark.parametrize("cik", ["320193", APPLE_CIK, "CIK0000320193"])
def test_valid_cik_narrows_to_that_company(api_client, two_companies, cik: str) -> None:
    r = api_client.get(URL, {"q": "revenue", "cik": cik})
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    assert body["count"] == 1
    assert [row["cik"] for row in body["results"]] == [APPLE_CIK]


@pytest.mark.parametrize("params", [{"q": "revenue"}, {"q": "revenue", "cik": ""}])
def test_missing_or_empty_cik_searches_every_company(api_client, two_companies, params) -> None:
    r = api_client.get(URL, params)
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    assert body["count"] == 2
    assert {row["cik"] for row in body["results"]} == {APPLE_CIK, MSFT_CIK}
