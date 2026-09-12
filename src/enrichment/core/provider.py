"""Provider protocol and registry.

A provider declares what it NEEDS and what it YIELDS. The runner uses those
declarations to decide when - and whether - to call it. That is the whole
difference between a framework and a script with a lot of if-statements:
adding a new source means writing one class, not editing the orchestrator.

    class MyProvider(Provider):
        name = "my_source"
        requires = {"website"}        # only runs once a website is known
        provides = {"employees"}
        cost = Cost.FETCH             # one HTTP call per record
        rate_per_sec = 2.0

        def run(self, rec, ctx):
            yield Claim(field="employees", value=..., confidence=0.6,
                        provider=self.name, evidence=Evidence(url=...))
"""

from __future__ import annotations

from typing import Iterable, Protocol

from .model import Claim, Record


class Cost:
    """How expensive a provider is per record - drives scheduling and budgets."""

    FREE = "free"  # pure computation, no I/O (name parsing, heuristics)
    BULK = "bulk"  # one download amortised across the whole list
    API = "api"  # one structured API call per record
    FETCH = "fetch"  # one or more page fetches per record - slowest, rate-limited
    SEARCH = "search"  # a search-engine query - slowest and most rate-limited


COST_ORDER = {Cost.FREE: 0, Cost.BULK: 1, Cost.API: 2, Cost.FETCH: 3, Cost.SEARCH: 4}


class Provider(Protocol):
    name: str
    requires: frozenset[str]
    provides: frozenset[str]
    cost: str
    rate_per_sec: float

    def run(self, rec: Record, ctx) -> Iterable[Claim]: ...


class BaseProvider:
    """Convenience base. Subclasses set the class attributes and implement run()."""

    name: str = "unnamed"
    requires: frozenset[str] = frozenset()
    provides: frozenset[str] = frozenset()
    cost: str = Cost.FREE
    rate_per_sec: float = 1000.0
    # If True the runner calls prepare() once before the pass (bulk downloads).
    needs_prepare: bool = False

    # Providers that should get their turn first, named rather than required.
    #
    # `requires` is about fields a provider CANNOT run without; this is about
    # fields that would change its answer if they arrived. The distinction
    # matters because the runner fires providers cheapest-first within a wave, so
    # a free provider reading a field that an API provider supplies runs too
    # early and answers from the seed. That produced a modelled revenue for a
    # company whose CIK lookup had not happened yet, and a sector classification
    # from a supplier list's end-market tags rather than from the SIC code SEC
    # holds for that filer.
    #
    # Deferring is a preference, not a precondition. The runner enforces it and
    # then DROPS it once a record has gone quiet — otherwise a provider waiting
    # on one that never becomes eligible for this particular record waits
    # forever. That is not hypothetical: `fred` and `revenue_model` defer to
    # `edgar_submissions`, which only fires for SEC filers, and enforcing the
    # wait unconditionally left 10,625 of 10,982 records with no macro context
    # and no revenue estimate at all. A private company still gets both; it gets
    # them after EDGAR has confirmed it has nothing to say.
    defer_to: frozenset[str] = frozenset()
    # Set by the runner to `defer_to` narrowed to the providers in THIS pass.
    _active_defer: frozenset[str] = frozenset()

    def prepare(self, ctx) -> None:
        """Download/index anything shared across all records. Called at most once."""

    def eligible(self, rec: Record) -> bool:
        """Default: run when inputs are present and we'd add something new.

        Says nothing about `defer_to`: that is scheduling, and the runner owns
        scheduling. Overrides can call super() without knowing about wave order.
        """
        if not self.requires <= rec.available():
            return False
        # Skip if every field we provide is already verified by someone else.
        return not all(any(c.verified for c in rec.claims_for(f)) for f in self.provides)

    def run(self, rec: Record, ctx) -> Iterable[Claim]:
        raise NotImplementedError


class Registry:
    def __init__(self):
        self._providers: dict[str, BaseProvider] = {}

    def register(self, p: BaseProvider) -> BaseProvider:
        if p.name in self._providers:
            raise ValueError(f"duplicate provider name: {p.name}")
        self._providers[p.name] = p
        return p

    def get(self, name: str) -> BaseProvider:
        return self._providers[name]

    def all(self) -> list[BaseProvider]:
        """Cheapest first - so free inference runs before anything hits the network."""
        return sorted(self._providers.values(), key=lambda p: (COST_ORDER.get(p.cost, 9), p.name))

    def names(self) -> list[str]:
        return [p.name for p in self.all()]

    def plan(self, available: frozenset[str]) -> list[list[str]]:
        """Which providers could fire, in waves, given a starting field set.

        Pure planning - no records touched. This is what `manage.py enrich_plan`
        prints: "what would this framework actually do to my list?", answered
        before you spend a single request.
        """
        have: set[str] = set(available)
        waves: list[list[str]] = []
        used: set[str] = set()
        while True:
            wave = [p.name for p in self.all() if p.name not in used and p.requires <= have]
            if not wave:
                return waves
            waves.append(wave)
            used.update(wave)
            for n in wave:
                have |= set(self._providers[n].provides)
