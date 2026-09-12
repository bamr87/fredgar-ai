"""Regression tests for website verification.

Every case here is one that has already gone wrong once. The Eaton / Eaton Vance
pair in particular: a naive prefix match verified a completely unrelated
investment firm as a power-management manufacturer's website, at 0.99
confidence, and every attribute harvested from that page would have been wrong
with no error raised anywhere.

These are pure functions over saved HTML — no database, no network.
"""

import pathlib

from enrichment.providers.webdiscovery import (
    is_aggregator,
    name_agreement,
    parse_page,
    registrable_domain,
    title_agreement,
    verify_site,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return parse_page((FIXTURES / name).read_text())


CASES = [
    ("Eaton Corporation plc HQ", "https://www.eaton.com", "eaton.html", True),
    ("Metalsa S. de R.L. de C.V.", "https://www.metalsa.com", "graph_site.html", True),
    ("Gibbens Industries Pty Ltd", "https://gibbens.com.au", "bare.html", True),
    ("Acme Corporation", "https://acmecorp.com", "parked.html", False),
    ("Eaton Corporation plc", "https://eatonvance.com", "wrong_co.html", False),
    ("Lear Corporation", "https://bloomberg.com/profile/lear", "aggregator.html", False),
]


def test_verification_matrix():
    for name, url, fixture, expected in CASES:
        ok, confidence, why = verify_site(name, url, load(fixture))
        assert ok is expected, f"{name} vs {fixture}: got {ok} ({confidence}, {why})"


def test_distinctive_extra_token_blocks_match():
    """A site stating an identity that is not yours is evidence AGAINST, not absence."""
    assert name_agreement("Eaton Corporation plc", "Eaton Vance Corp")[0] < 0.5
    assert name_agreement("Lear Corporation", "Lear Capital LLC")[0] < 0.5
    assert name_agreement("Metalsa S. de R.L. de C.V.", "Metalsa")[0] >= 0.9


def test_title_never_carries_a_single_token_name():
    """Titles carry taglines, so they match on coverage — and never alone."""
    assert title_agreement("Eaton Corporation plc", "Eaton Vance | Investing")[0] == 0.0
    assert (
        title_agreement("Gibbens Industries Pty Ltd", "Gibbens Industries Pty Ltd - Components")[0]
        == 1.0
    )


def test_domain_parsing():
    assert registrable_domain("https://www.eaton.com/us/en") == "eaton.com"
    assert registrable_domain("http://sub.acme.co.uk/x") == "acme.co.uk"
    assert is_aggregator("https://www.linkedin.com/company/x")
    assert not is_aggregator("https://www.eaton.com")


def test_jsonld_harvest_including_graph_form():
    page = load("eaton.html")
    assert page["org_legal_name"] == "Eaton Corporation plc"
    assert page["org_employees"] == 92000
    assert len(page["org_same_as"]) == 3

    nested = load("graph_site.html")  # Organization nested inside @graph
    assert nested["org_legal_name"] == "Metalsa S. de R.L. de C.V."
    assert nested["org_locality"] == "Monterrey"


def test_parked_domain_is_not_a_website():
    ok, confidence, why = verify_site(
        "Acme Corporation", "https://acmecorp.com", load("parked.html")
    )
    assert ok is False
    assert "parked" in why
