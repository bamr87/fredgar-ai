"""The web-discovery providers end to end, against fixtures instead of the web.

`test_verify.py` covers the scoring functions. This covers what the *providers*
do with them: which candidates get fetched, what happens when a fetch fails, and
— the part that matters — whether an unverified domain can ever reach the record
as a `website`.
"""

from enrichment.core.model import Record
from enrichment.core.runner import Context
from enrichment.providers.webdiscovery import DomainCandidates, SearchDiscovery, SiteProbe

from .mockhttp import MockHttp, MockSearch


def make_record(name: str, **fields) -> Record:
    from enrichment.normalize import blocking_key, clean

    seed = {"name": name, "clean_name": clean(name), "blocking_key": blocking_key(name)}
    seed.update(fields)
    return Record(1, name, seed)


def with_candidates(name: str, *urls, **fields) -> Record:
    from enrichment.core.model import Claim, Evidence

    rec = make_record(name, **fields)
    for url in urls:
        rec.add(Claim("website_candidate", url, 0.25, "domain_guess", Evidence()))
    rec.fields["website_candidate"] = urls[0]
    return rec


def run(provider, rec, ctx):
    return list(provider.run(rec, ctx))


# ----------------------------------------------------------- domain guessing --


def test_guesses_are_candidates_never_websites():
    """`domain_guess` may not produce a `website`. Only verification can."""
    claims = run(DomainCandidates(), make_record("Gibbens Industries Pty Ltd"), Context())
    assert claims
    assert {c.field for c in claims} == {"website_candidate"}
    assert not any(c.verified for c in claims)


def test_country_aware_tlds():
    claims = run(
        DomainCandidates(), make_record("Gibbens Industries Pty Ltd", country_iso="AU"), Context()
    )
    assert any(c.value.endswith(".com.au") for c in claims)


def test_generic_and_geographic_lead_words_are_not_used_as_stems():
    """ "Shanghai Something" must not guess shanghai.cn, and "Custom X" not custom.com.

    Both produced confident guesses at entirely unrelated companies when measured
    against the live web.
    """
    claims = run(
        DomainCandidates(), make_record("Shanghai Yinzuo Precision", country_iso="CN"), Context()
    )
    assert not any(c.value.startswith("https://shanghai.") for c in claims)

    claims = run(DomainCandidates(), make_record("Custom Mold & Design"), Context())
    assert not any(c.value.startswith("https://custom.") for c in claims)


# ------------------------------------------------------------------- probing --


def test_a_verified_site_yields_the_website_and_its_attributes():
    http = MockHttp({"eaton.com": "eaton.html"})
    rec = with_candidates("Eaton Corporation plc HQ", "https://eaton.com")

    claims = run(SiteProbe(), rec, Context(http=http))
    single = {c.field: c for c in claims if c.field != "reference"}

    assert single["website"].verified is True
    assert single["legal_name"].value == "Eaton Corporation plc"
    assert single["employees_site"].value == 92000
    # Attributes harvested from a page are attributed to the page, not the prober.
    assert single["legal_name"].provider == "site_jsonld"

    # schema.org sameAs is the richest reference source a site can hand you.
    references = [c for c in claims if c.field == "reference"]
    assert len(references) == 3
    assert all(r.evidence.locator == "jsonld:sameAs" for r in references)


def test_a_dead_domain_is_skipped_and_the_next_candidate_is_tried():
    """The common case: most guessed domains do not resolve."""
    http = MockHttp({"eaton.com": "eaton.html"})
    rec = with_candidates(
        "Eaton Corporation plc HQ", "https://eatoncorporation.com", "https://eaton.com"
    )

    claims = {c.field: c for c in run(SiteProbe(), rec, Context(http=http))}

    assert len(http.calls) == 2
    assert claims["website"].verified is True


def test_every_candidate_failing_claims_nothing():
    http = MockHttp({})
    rec = with_candidates("Nowhere Industries Ltd", "https://nowhere.com", "https://nowhere.net")

    assert run(SiteProbe(), rec, Context(http=http)) == []


def test_a_parked_domain_never_becomes_a_website():
    http = MockHttp({"acmecorp.com": "parked.html"})
    rec = with_candidates("Acme Corporation", "https://acmecorp.com")

    assert run(SiteProbe(), rec, Context(http=http)) == []


def test_somebody_elses_site_never_becomes_a_website():
    """The Eaton Vance case, through the provider rather than the scorer.

    A wrong site does not fail loudly — every attribute on it would flow into the
    record with a plausible evidence URL attached.
    """
    http = MockHttp({"eatonvance.com": "wrong_co.html"})
    rec = with_candidates("Eaton Corporation plc", "https://eatonvance.com")

    assert run(SiteProbe(), rec, Context(http=http)) == []


def test_probing_stops_at_the_candidate_cap():
    """`--max-fetch` is the run's budget; `max_candidates` is the record's."""
    http = MockHttp({})
    rec = with_candidates("Nowhere Industries Ltd", *[f"https://n{i}.com" for i in range(10)])

    run(SiteProbe(), rec, Context(http=http))
    assert len(http.calls) == SiteProbe.max_candidates


def test_no_http_client_means_no_claims_rather_than_a_crash():
    """`--no-web` runs must leave the fetch providers silent, not broken."""
    rec = with_candidates("Eaton Corporation plc HQ", "https://eaton.com")
    assert run(SiteProbe(), rec, Context(http=None)) == []


# -------------------------------------------------------------------- search --


def test_aggregators_are_captured_as_references_never_as_websites():
    """LinkedIn is an excellent reference and a terrible website."""
    search = MockSearch(
        {
            "Lear": [
                {"url": "https://www.linkedin.com/company/lear", "title": "Lear | LinkedIn"},
                {"url": "https://lear.com", "title": "Lear Corporation"},
            ]
        }
    )
    ctx = Context(shared={"search": search})
    claims = run(SearchDiscovery(), make_record("Lear Corporation"), ctx)

    by_field = {}
    for c in claims:
        by_field.setdefault(c.field, []).append(c.value)

    assert by_field["reference"][0]["url"].startswith("https://www.linkedin.com/")
    assert by_field["website_candidate"] == ["https://lear.com"]


def test_search_does_not_fire_once_a_website_is_verified():
    """The expensive provider only pays where the free path failed."""
    from enrichment.core.model import Claim, Evidence

    rec = make_record("Lear Corporation")
    rec.add(Claim("website", "https://lear.com", 0.9, "site_probe", Evidence(), verified=True))

    assert SearchDiscovery().eligible(rec) is False


def test_search_is_silent_without_a_backend():
    assert run(SearchDiscovery(), make_record("Lear Corporation"), Context()) == []
