"""The framework's own guarantees: resolution, resumability, isolation, budgets.

These are the properties the whole design is for. If they hold, a bad provider
costs you one field; if they do not, it costs you the run.
"""

import pytest

from enrichment.core import store
from enrichment.core.golden import resolve_record, write_golden
from enrichment.core.model import Claim, Evidence, Record
from enrichment.core.provider import BaseProvider, Cost, Registry
from enrichment.core.runner import Budget, Context, Runner
from enrichment.services import refresh_providers, resolve_dataset
from warehouse.models import (
    EnrichmentClaim,
    EnrichmentDataset,
    EnrichmentGoldenField,
    EnrichmentProviderRun,
    EnrichmentRecord,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def dataset():
    ds = EnrichmentDataset.objects.create(slug="t", name="Test list")
    for name in ("Acme Industries Ltd", "Beta Works GmbH", "Gamma Tooling SA"):
        store.upsert_record(ds, name, {"name": name, "clean_name": name.lower()})
    return ds


def claim(field, value, confidence, provider, verified=False, url="http://x"):
    return Claim(field, value, confidence, provider, Evidence(url=url), verified)


# ------------------------------------------------------------------ golden --


def test_precedence_beats_confidence():
    """A verified registry value at 0.70 outranks a confident guess at 0.95."""
    rec = Record(1, "x")
    rec.add(claim("legal_name", "Guessed Name", 0.95, "domain_guess"))
    rec.add(claim("legal_name", "Filed Name", 0.70, "edgar_submissions", verified=True))

    assert resolve_record(rec)["legal_name"]["value"] == "Filed Name"


def test_a_filed_number_outranks_a_model():
    rec = Record(1, "x")
    rec.add(claim("revenue_estimated", 5e9, 0.9, "revenue_model"))
    rec.add(claim("revenue_reported", 2.7e10, 0.97, "edgar_facts", verified=True))

    resolved = resolve_record(rec)
    assert resolved["revenue_reported"]["value"] == 2.7e10
    # The two live in separate fields and are never averaged into one number.
    assert resolved["revenue_estimated"]["value"] == 5e9


def test_comparable_sources_disagreeing_is_contested():
    """Contested is a review queue, not an error.

    Eaton is the live example: SEC's entity record gives Dublin (where the plc is
    domiciled) and its own website gives Beachwood (where the business is run).
    Both are true, neither is the other, and a human should decide which one a
    vendor master wants. Precedence still picks SEC — contested says "look".
    """
    rec = Record(1, "x")
    rec.add(claim("hq_city", "Dublin", 0.93, "edgar_submissions"))
    rec.add(claim("hq_city", "Beachwood", 0.90, "site_probe"))

    resolved = resolve_record(rec)["hq_city"]
    assert resolved["value"] == "Dublin"
    assert resolved["contested"] == 1


def test_a_filing_beating_a_guess_is_not_contested():
    """Sources tiers apart are not peers, and a wide gap needs nobody's attention."""
    rec = Record(1, "x")
    rec.add(claim("website", "https://eaton.com", 0.95, "edgar_facts", verified=True))
    rec.add(claim("website", "https://eatoncorp.com", 0.90, "domain_guess"))

    assert resolve_record(rec)["website"]["contested"] == 0


def test_multi_valued_fields_keep_every_value():
    """One record legitimately sits in several macro contexts and carries many flags."""
    rec = Record(1, "x")
    rec.add(claim("validation_reason", "form_country_mismatch:plc~US", 0.9, "jurisdiction"))
    rec.add(claim("validation_reason", "edgar_ambiguous_name:2_filers", 0.9, "edgar_issuer"))

    reasons = resolve_record(rec)["validation_reason"]["value"]
    assert len(reasons) == 2


def test_golden_is_rebuilt_not_appended(dataset):
    record = EnrichmentRecord.objects.filter(dataset=dataset).first()
    rec = Record(record.pk, record.source_key, dict(record.seed))
    rec.add(claim("legal_name", "First", 0.9, "site_probe"))
    write_golden(record.pk, rec)

    rec2 = Record(record.pk, record.source_key, dict(record.seed))
    rec2.add(claim("legal_name", "Second", 0.9, "site_probe"))
    write_golden(record.pk, rec2)

    rows = EnrichmentGoldenField.objects.filter(record=record, field="legal_name")
    assert rows.count() == 1
    assert rows.first().value == "Second"


# ------------------------------------------------------------------- store --


def test_a_record_is_rebuilt_from_claims_not_from_the_field_cache(dataset):
    """Deleting a provider's claims must delete its contribution.

    Keeping only the promoted ``fields`` cache was a silent correctness hole: the
    corrected re-run read the very state it was meant to replace.
    """
    record = EnrichmentRecord.objects.filter(dataset=dataset).first()
    store.save_claims(record.pk, [claim("legal_name", "From Provider", 0.9, "site_probe")])
    store.set_fields(record.pk, {**record.seed, "legal_name": "From Provider"})

    assert store.load_record(EnrichmentRecord.objects.get(pk=record.pk)).get("legal_name")

    EnrichmentClaim.objects.filter(record=record, provider="site_probe").delete()
    reloaded = store.load_record(EnrichmentRecord.objects.get(pk=record.pk))
    assert reloaded.get("legal_name") is None


def test_re_saving_the_same_claim_does_not_duplicate_it(dataset):
    record = EnrichmentRecord.objects.filter(dataset=dataset).first()
    for _ in range(3):
        store.save_claims(record.pk, [claim("sic", "3590", 0.97, "edgar_submissions")])
    assert EnrichmentClaim.objects.filter(record=record, field="sic").count() == 1


def test_refresh_drops_one_provider_and_leaves_the_others(dataset):
    record = EnrichmentRecord.objects.filter(dataset=dataset).first()
    store.save_claims(
        record.pk,
        [
            claim("legal_name", "A", 0.9, "site_probe"),
            claim("sic", "3590", 0.97, "edgar_submissions"),
        ],
    )
    store.mark_run(record.pk, "site_probe", "ok", None, None)
    store.mark_run(record.pk, "edgar_submissions", "ok", None, None)

    refresh_providers(dataset, ["site_probe"])

    assert not EnrichmentClaim.objects.filter(record=record, provider="site_probe").exists()
    assert EnrichmentClaim.objects.filter(record=record, provider="edgar_submissions").exists()
    assert not EnrichmentProviderRun.objects.filter(record=record, provider="site_probe").exists()


# ------------------------------------------------------------------ runner --


class Counter(BaseProvider):
    name = "counter"
    requires = frozenset({"name"})
    provides = frozenset({"counted"})
    cost = Cost.FREE

    def __init__(self):
        self.calls = 0

    def run(self, rec, ctx):
        self.calls += 1
        yield claim("counted", self.calls, 0.5, self.name)


class Exploder(BaseProvider):
    name = "exploder"
    requires = frozenset({"name"})
    provides = frozenset({"never"})
    cost = Cost.FREE

    def run(self, rec, ctx):
        raise RuntimeError("provider is broken")


class Fetcher(BaseProvider):
    name = "fetcher"
    requires = frozenset({"name"})
    provides = frozenset({"fetched"})
    cost = Cost.FETCH

    def run(self, rec, ctx):
        yield claim("fetched", True, 0.5, self.name)


def test_a_second_run_reruns_nothing(dataset):
    """Resumability: every (record, provider) attempt is checkpointed."""
    counter = Counter()
    registry = Registry()
    registry.register(counter)

    Runner(registry, dataset, workers=1).run()
    assert counter.calls == 3

    Runner(registry, dataset, workers=1).run()
    assert counter.calls == 3  # nothing re-ran
    assert EnrichmentClaim.objects.filter(field="counted").count() == 3


def test_one_provider_raising_loses_neither_the_row_nor_the_run(dataset):
    registry = Registry()
    registry.register(Exploder())
    registry.register(Counter())

    stats = Runner(registry, dataset, workers=1).run()

    assert stats["errors"] == 3
    assert EnrichmentClaim.objects.filter(field="counted").count() == 3
    errors = EnrichmentProviderRun.objects.filter(provider="exploder", status="error")
    assert errors.count() == 3
    assert "provider is broken" in errors.first().detail


def test_a_budget_stops_its_cost_class_not_the_run(dataset):
    registry = Registry()
    registry.register(Fetcher())
    registry.register(Counter())

    ctx = Context(budget=Budget(max_fetch=2))
    stats = Runner(registry, dataset, ctx, workers=1).run()

    assert EnrichmentClaim.objects.filter(field="fetched").count() == 2
    assert stats["skipped"] == 1
    assert EnrichmentClaim.objects.filter(field="counted").count() == 3  # free work unaffected


def test_deferral_only_waits_for_providers_in_this_pass(dataset):
    """`--only` must not deadlock a provider waiting on something excluded."""

    class Waiter(Counter):
        name = "waiter"
        defer_to = frozenset({"counter"})

    registry = Registry()
    waiter = Waiter()
    registry.register(waiter)
    registry.register(Counter())

    Runner(registry, dataset, workers=1).run(only=["waiter"])
    assert waiter.calls == 3  # ran, because `counter` was not in this pass


def test_deferral_does_not_starve_a_provider_waiting_on_an_ineligible_one(dataset):
    """The regression that cost 10,625 records their revenue estimate.

    `revenue_model` defers to `edgar_facts`, which requires a CIK — and most
    records are private companies that will never have one. Enforcing the wait
    unconditionally meant those records were never enriched at all. Deferral must
    yield once the record has gone quiet.
    """

    class NeedsCik(BaseProvider):
        name = "needs_cik"
        requires = frozenset({"cik"})  # never satisfied for these records
        provides = frozenset({"filed"})
        cost = Cost.FREE

        def run(self, rec, ctx):  # pragma: no cover - never eligible here
            yield claim("filed", True, 0.9, self.name)

    class Waiter(Counter):
        name = "waiter"
        defer_to = frozenset({"needs_cik"})

    registry = Registry()
    waiter = Waiter()
    registry.register(NeedsCik())
    registry.register(waiter)

    Runner(registry, dataset, workers=1).run()

    assert waiter.calls == 3
    assert EnrichmentClaim.objects.filter(field="filed").count() == 0


def test_deferral_still_orders_providers_that_can_run(dataset):
    """Yielding at the end must not make the deferral meaningless in normal cases."""
    order = []

    class First(BaseProvider):
        name = "first"
        requires = frozenset({"name"})
        provides = frozenset({"a"})
        cost = Cost.API  # more expensive, so it would sort AFTER the waiter

        def run(self, rec, ctx):
            order.append("first")
            yield claim("a", 1, 0.9, self.name)

    class Second(BaseProvider):
        name = "second"
        requires = frozenset({"name"})
        provides = frozenset({"b"})
        cost = Cost.FREE
        defer_to = frozenset({"first"})

        def run(self, rec, ctx):
            order.append("second")
            yield claim("b", 2, 0.9, self.name)

    registry = Registry()
    registry.register(First())
    registry.register(Second())

    Runner(registry, dataset, workers=1).run(limit=1)
    assert order == ["first", "second"]


def test_resolve_dataset_writes_golden_for_every_record_with_claims(dataset):
    registry = Registry()
    registry.register(Counter())
    Runner(registry, dataset, workers=1).run()

    stats = resolve_dataset(dataset)
    assert stats["records_resolved"] == 3
    assert EnrichmentGoldenField.objects.filter(record__dataset=dataset).count() == 3


# ------------------------------------------------------------------ wiring --


def test_offline_runs_still_guess_domains():
    """`--no-web` gates the network, not offline inference.

    `domain_guess` proposes candidates by string manipulation and makes no
    requests, but it was registered behind the web switch — so
    `--no-web --only domain_guess` reported a clean run and produced nothing.
    A flag that silently does nothing is worse than one that errors.
    """
    from enrichment.pipeline import default_registry

    offline = default_registry(enable_web=False)
    assert "domain_guess" in offline.names()
    assert "site_probe" not in offline.names()

    online = default_registry(enable_web=True)
    assert "site_probe" in online.names()


def test_search_and_geocode_stay_off_unless_asked():
    """Both need infrastructure the operator has to supply."""
    from enrichment.pipeline import default_registry

    assert "web_search" not in default_registry().names()
    assert "geocode" not in default_registry().names()
    assert "web_search" in default_registry(enable_search=True).names()
    assert "geocode" in default_registry(enable_geocode=True).names()


def test_every_registered_provider_declares_a_known_cost():
    """Cost drives both scheduling order and which budget a provider draws on."""
    from enrichment.core.provider import COST_ORDER
    from enrichment.pipeline import default_registry

    registry = default_registry(enable_search=True, enable_geocode=True)
    for p in registry.all():
        assert p.cost in COST_ORDER, f"{p.name} has unknown cost {p.cost!r}"
        assert p.provides, f"{p.name} yields nothing"
