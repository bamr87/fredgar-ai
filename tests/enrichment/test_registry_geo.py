"""Regression tests for jurisdiction validation and geographic normalization.

Every case here came from auditing what the reference tables produced against
10,982 real records. The two bug classes they guard:

1. **Ambiguity leaking through decomposition.** "corporation" is not literally in
   the ambiguous-forms list, but decomposes to "corp", which is. Before this was
   fixed, generic English descriptors generated 129 of 364 jurisdiction flags — a
   third of the review queue, every one a false positive.

2. **Over-correcting with a prefix test.** The first fix condemned any token
   starting with an ambiguous root, which broke "sarl" (starts with "sa") and
   would have broken every legitimate long form beginning with two ambiguous
   letters.

Both are the same underlying mistake: a filter that is wrong about what it
*rejects* looks exactly like one that works, because nobody inspects the rejects.
"""

from enrichment.normalize import extract_legal_forms
from enrichment.providers.geo import resolve_country
from enrichment.reference.registries import (
    is_ambiguous,
    jurisdictions_for_form,
    registry_for,
)


def test_generic_descriptors_are_ambiguous():
    """These are used by companies in every jurisdiction on earth."""
    for form in (
        "corporation",
        "incorporated",
        "companylimited",
        "coltd",
        "company",
        "limited",
        "holdings",
    ):
        assert is_ambiguous(form), form


def test_specific_forms_survive_the_ambiguity_check():
    """ "sarl" begins with the ambiguous "sa" and is a real, specific form."""
    for form in ("sarl", "gmbh", "kk", "sdnbhd", "sderldecv", "spzoo", "pty", "kft"):
        assert not is_ambiguous(form), form


def test_composite_forms_resolve_through_decomposition():
    assert jurisdictions_for_form("sderldecv") == {"MX"}
    assert jurisdictions_for_form("sdnbhd") == {"MY", "BN"}
    assert jurisdictions_for_form("gmbhcokg") == {"DE", "AT"}
    assert jurisdictions_for_form("kk") == {"JP"}


def test_francophone_africa_coverage():
    """20 Algerian SARLs were flagged inconsistent by a table that knew only France.

    SARL and SPA are standard across the Maghreb. This is what auditing the
    *rejects* surfaces — the bias lives in what a filter throws away.
    """
    assert "DZ" in jurisdictions_for_form("sarl")
    assert "TN" in jurisdictions_for_form("sarl")
    assert "CI" in jurisdictions_for_form("sarl")
    assert "DZ" in jurisdictions_for_form("spa")


def test_gulf_states_use_llc():
    for country in ("AE", "OM", "QA", "KW", "SA"):
        assert country in jurisdictions_for_form("llc"), country


def test_legal_form_extraction():
    """`clean()` strips these as matching noise; validation needs them back."""
    assert extract_legal_forms("Robert Bosch GmbH & Co. KG")[0] == "gmbh"
    assert "sderldecv" in extract_legal_forms("Metalsa S. de R.L. de C.V.")
    assert extract_legal_forms("Acme") == []


def test_country_resolution_never_guesses():
    assert resolve_country("United States") == "US"
    assert resolve_country("Czech Republic") == "CZ"
    assert resolve_country("South Korea") == "KR"
    assert resolve_country("Macao") == "MO"
    assert resolve_country("DE") == "DE"
    # An unresolvable country must be None, not a plausible code.
    assert resolve_country("Freedonia") is None
    assert resolve_country(None) is None


def test_registry_routing_falls_back_to_gleif():
    assert "Companies House" in registry_for("GB")["name"]
    assert registry_for("VN")["scope"] == "global"  # no national entry
    assert registry_for(None)["scope"] == "global"


def test_us_records_are_routed_to_edgar():
    """The register this repo actually implements a provider for."""
    us = registry_for("US")
    assert us["scope"] == "national"
    assert "sec.gov" in us["url"]
    assert us["free_api"] is True


def test_free_api_flag_marks_the_registers_worth_writing_next():
    """`registry_free_api` is the backlog: which provider to build after EDGAR."""
    for country in ("GB", "FR", "NO", "DK", "FI", "CZ", "PL"):
        assert registry_for(country)["free_api"] is True, country
