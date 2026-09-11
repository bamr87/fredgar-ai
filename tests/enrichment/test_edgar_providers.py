"""The SEC providers: matching, database-first reads, and fact selection.

The expensive failure mode here is silent, not loud: a wrong CIK attaches another
company's audited financials to a vendor record with a plausible sec.gov URL
beside it. Most of these tests exist to keep that from happening.
"""

import pytest
from django.utils import timezone

from enrichment.core.model import Record
from enrichment.core.runner import Context
from enrichment.providers.edgar import (
    EdgarFacts,
    EdgarIssuerMatch,
    EdgarSubmissions,
    _latest_annual,
    build_issuer_index,
)
from warehouse.models import EdgarSecPayload, ListedIssuer

pytestmark = pytest.mark.django_db


def make_record(name: str, **fields) -> Record:
    from enrichment.normalize import blocking_key, clean

    seed = {"name": name, "clean_name": clean(name), "blocking_key": blocking_key(name)}
    seed.update(fields)
    return Record(1, name, seed)


def seed_issuers(*rows):
    now = timezone.now()
    ListedIssuer.objects.bulk_create(
        ListedIssuer(cik=cik, ticker=ticker, name=name, synced_at=now) for cik, ticker, name in rows
    )


def run(provider, rec, ctx=None):
    ctx = ctx or Context()
    if getattr(provider, "needs_prepare", False):
        provider.prepare(ctx)
    return list(provider.run(rec, ctx))


# ------------------------------------------------------------- issuer match --


def test_exact_name_match_verifies_the_cik():
    seed_issuers(("0001551182", "ETN", "Eaton Corp plc"))
    claims = run(EdgarIssuerMatch(), make_record("Eaton Corp plc"))

    by_field = {c.field: c for c in claims}
    assert by_field["cik"].value == "0001551182"
    assert by_field["cik"].verified is True
    assert by_field["ticker"].value == "ETN"
    assert "sec.gov" in by_field["cik"].evidence.url


def test_legal_noise_does_not_make_a_match_inexact():
    """`clean()` strips legal forms and site qualifiers, so these are the same name.

    "Eaton Corporation plc HQ" and "Eaton Corp plc" both normalise to "eaton" —
    which is the entire purpose of normalisation, and why the match verifies.
    """
    seed_issuers(("0001551182", "ETN", "Eaton Corp plc"))
    claims = run(EdgarIssuerMatch(), make_record("Eaton Corporation plc HQ"))

    cik = next(c for c in claims if c.field == "cik")
    assert cik.value == "0001551182"
    assert cik.verified is True


def test_a_distinctive_extra_token_is_never_even_compared():
    """Blocking on the token SET is what stops the Eaton/Eaton Vance failure here.

    ``score_match`` contains a prefix rule that would score "Eaton Aerospace"
    against "Eaton Corp plc" at 0.90 — the same shape as the website bug, where a
    naive prefix test verified an unrelated investment firm. It never gets the
    chance: the blocking key is the sorted token set, so a name carrying an extra
    distinctive token lands in a different block and is not a candidate at all.

    This is the structural version of the verifier's ``distinctive_extra`` rule,
    and it is why the matcher can afford a prefix rule at all.
    """
    seed_issuers(("0001551182", "ETN", "Eaton Corp plc"))
    assert run(EdgarIssuerMatch(), make_record("Eaton Aerospace LLC")) == []


def test_two_filers_with_the_same_name_verify_neither():
    """A tie is ambiguity, not a close call. Picking one is indefensible."""
    seed_issuers(
        ("0000001111", "DLA", "Delta Industries Inc"),
        ("0000002222", "DLB", "Delta Industries Inc"),
    )
    claims = run(EdgarIssuerMatch(), make_record("Delta Industries Inc"))

    assert not any(c.verified for c in claims)
    reasons = [c.value for c in claims if c.field == "validation_reason"]
    assert any("edgar_ambiguous_name" in r for r in reasons)


def test_unknown_name_claims_nothing():
    seed_issuers(("0001551182", "ETN", "Eaton Corp plc"))
    assert run(EdgarIssuerMatch(), make_record("Gibbens Industries Pty Ltd")) == []


def test_issuer_index_blocks_by_normalised_name():
    seed_issuers(("0001551182", "ETN", "Eaton Corp plc"))
    index = build_issuer_index()
    assert "eaton" in index
    assert index["eaton"][0]["cik"] == "0001551182"


# --------------------------------------------------------------- submissions --

SUBMISSIONS = {
    "name": "Eaton Corp plc",
    "sic": "3590",
    "sicDescription": "Misc Industrial & Commercial Machinery & Equipment",
    "ein": "981059235",
    "stateOfIncorporation": "L2",
    "entityType": "operating",
    "fiscalYearEnd": "1231",
    "phone": "353 1 637 2900",
    "tickers": ["ETN"],
    "exchanges": ["NYSE"],
    "formerNames": [{"name": "Eaton Corp Ltd"}],
    "addresses": {
        "business": {
            "city": "DUBLIN",
            "stateOrCountry": "L2",
            "stateOrCountryDescription": "IRELAND",
            "zipCode": "D18 K7W7",
            "street1": "EATON HOUSE",
        },
        "mailing": {"city": "WILMINGTON", "stateOrCountry": "DE"},
    },
}


def test_submissions_reads_the_cached_payload_without_touching_sec(settings):
    """Database-first is the point: a cached payload must not produce a request."""
    EdgarSecPayload.objects.create(
        cik="0001551182",
        kind=EdgarSecPayload.Kind.SUBMISSIONS,
        payload=SUBMISSIONS,
        fetched_at=timezone.now(),
    )
    claims = run(EdgarSubmissions(), make_record("Eaton", cik="0001551182"))
    by_field = {c.field: c.value for c in claims}

    assert by_field["legal_name"] == "Eaton Corp plc"
    assert by_field["sic"] == "3590"
    assert by_field["ein"] == "981059235"
    assert by_field["fiscal_year_end"] == "1231"


def test_submissions_takes_the_business_address_not_the_mailing_one():
    """A registered-agent mailbox in Delaware is not a place the company operates."""
    EdgarSecPayload.objects.create(
        cik="0001551182",
        kind=EdgarSecPayload.Kind.SUBMISSIONS,
        payload=SUBMISSIONS,
        fetched_at=timezone.now(),
    )
    claims = run(EdgarSubmissions(), make_record("Eaton", cik="0001551182"))
    cities = [c.value for c in claims if c.field == "hq_city"]
    assert cities == ["DUBLIN"]


def test_former_names_become_aliases():
    EdgarSecPayload.objects.create(
        cik="0001551182",
        kind=EdgarSecPayload.Kind.SUBMISSIONS,
        payload=SUBMISSIONS,
        fetched_at=timezone.now(),
    )
    claims = run(EdgarSubmissions(), make_record("Eaton", cik="0001551182"))
    assert [c.value for c in claims if c.field == "alias"] == ["Eaton Corp Ltd"]


# --------------------------------------------------------------------- facts --


def annual(concept, start, end, val, unit="USD"):
    return {"start": start, "end": end, "val": val, "form": "10-K", "fp": "FY", "fy": end[:4]}


def test_recency_beats_tag_preference():
    """The bug this exists for: a stray zero-valued tag outranking the real series.

    Eaton carries `Revenues` of 0 for 2015–2016 alongside a real
    `RevenueFromContractWithCustomerExcludingAssessedTax` series running to 2025.
    Preferring the first concept in the group produced a *verified* reported
    revenue of $0 with a citable SEC URL beside it.
    """
    facts = {
        "us-gaap": {
            "Revenues": {"units": {"USD": [annual("Revenues", "2016-01-01", "2016-12-31", 0)]}},
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {"USD": [annual("RFC", "2025-01-01", "2025-12-31", 27_448_000_000)]}
            },
        }
    }
    hit = _latest_annual(
        facts,
        "us-gaap",
        ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        duration=True,
    )
    assert hit["value"] == 27_448_000_000
    assert hit["end"] == "2025-12-31"


def test_preferred_tag_wins_only_when_periods_tie():
    facts = {
        "us-gaap": {
            "Revenues": {"units": {"USD": [annual("Revenues", "2024-01-01", "2024-12-31", 100)]}},
            "SalesRevenueNet": {"units": {"USD": [annual("SRN", "2024-01-01", "2024-12-31", 999)]}},
        }
    }
    hit = _latest_annual(facts, "us-gaap", ("Revenues", "SalesRevenueNet"), duration=True)
    assert hit["concept"] == "Revenues"


def test_quarterly_duration_is_never_mistaken_for_a_year():
    facts = {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        annual("Revenues", "2025-01-01", "2025-03-31", 5),  # a quarter
                        annual("Revenues", "2024-01-01", "2024-12-31", 400),
                    ]
                }
            }
        }
    }
    hit = _latest_annual(facts, "us-gaap", ("Revenues",), duration=True)
    assert hit["value"] == 400


def test_instant_facts_reject_duration_entries():
    """Headcount is an instant fact; an entry with a start date is a different thing."""
    facts = {
        "dei": {
            "EntityNumberOfEmployees": {
                "units": {
                    "pure": [
                        {"end": "2025-12-31", "val": 92000, "form": "10-K", "fp": "FY"},
                        annual("x", "2025-01-01", "2025-12-31", 1),
                    ]
                }
            }
        }
    }
    hit = _latest_annual(facts, "dei", ("EntityNumberOfEmployees",), duration=False)
    assert hit["value"] == 92000


def test_facts_claims_are_verified_and_cite_the_xbrl_locator():
    EdgarSecPayload.objects.create(
        cik="0001551182",
        kind=EdgarSecPayload.Kind.COMPANY_FACTS,
        payload={
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [annual("Revenues", "2024-01-01", "2024-12-31", 24_878_000_000)]
                        }
                    }
                }
            }
        },
        fetched_at=timezone.now(),
    )
    claims = run(EdgarFacts(), make_record("Eaton", cik="0001551182"))
    revenue = next(c for c in claims if c.field == "revenue_reported")

    assert revenue.value == 24_878_000_000
    assert revenue.verified is True
    assert revenue.evidence.locator.startswith("xbrl:us-gaap:Revenues:")
    assert "companyfacts" in revenue.evidence.url


# --------------------------------------------------- identity propagation ---


def test_sec_data_on_an_unverified_cik_is_not_verified():
    """Nothing derived from a guessed identity may outrank that identity.

    Without this, a near-miss CIK produced *verified* audited financials for the
    wrong company, with a data.sec.gov URL beside them — the Eaton Vance failure
    with a more authoritative-looking citation.
    """
    from enrichment.core.model import Claim, Evidence

    seed_issuers(("0001551182", "ETN", "Eaton Corp plc"))
    EdgarSecPayload.objects.create(
        cik="0001551182",
        kind=EdgarSecPayload.Kind.SUBMISSIONS,
        payload=SUBMISSIONS,
        fetched_at=timezone.now(),
    )
    EdgarSecPayload.objects.create(
        cik="0001551182",
        kind=EdgarSecPayload.Kind.COMPANY_FACTS,
        payload={
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {"USD": [annual("Revenues", "2024-01-01", "2024-12-31", 1_000)]}
                    }
                }
            }
        },
        fetched_at=timezone.now(),
    )

    rec = make_record("Eaton Aerospace LLC", cik="0001551182")
    rec.add(Claim("cik", "0001551182", 0.90, "edgar_issuer", Evidence(url="x"), verified=False))

    submissions = run(EdgarSubmissions(), rec)
    facts = run(EdgarFacts(), rec)

    assert not any(c.verified for c in submissions + facts)
    revenue = next(c for c in facts if c.field == "revenue_reported")
    assert revenue.confidence < 0.90  # scaled down by the identity's own confidence
    reasons = [c.value for c in submissions if c.field == "validation_reason"]
    assert any("sec_data_on_unverified_cik" in r for r in reasons)


def test_a_seeded_cik_is_trusted_as_the_lists_own_assertion():
    """If the input list supplied the CIK, its accuracy is the list's business."""
    EdgarSecPayload.objects.create(
        cik="0001551182",
        kind=EdgarSecPayload.Kind.SUBMISSIONS,
        payload=SUBMISSIONS,
        fetched_at=timezone.now(),
    )
    claims = run(EdgarSubmissions(), make_record("Eaton", cik="0001551182"))
    assert next(c for c in claims if c.field == "sic").verified is True
