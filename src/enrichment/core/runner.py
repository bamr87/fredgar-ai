"""The scheduler: iterate a list through the provider graph, resumably.

Three properties matter more than speed:

1. Resumable. Every (record, provider) attempt is checkpointed. Killing the
   process and restarting costs you at most the in-flight record.
2. Isolated. One provider raising on one record must not lose that record's
   other claims, and must not stop the run.
3. Budgeted. Network providers are capped explicitly, because the failure mode
   of an enrichment run is not "it crashed", it is "it quietly spent nine hours
   and got rate-limited into garbage".

Concurrency note: workers are threads, and Django connections are thread-local,
so each worker closes its own connection when it finishes. SQLite serialises
writers and deadlocks under concurrent writes, so :func:`safe_workers` clamps the
pool to 1 there — the cap is on the database, not on the framework.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from django.db import connection, connections, transaction

from . import store
from .model import NOW, Record
from .provider import Cost, Registry


def safe_workers(requested: int) -> int:
    """SQLite cannot take concurrent writers; everything else can."""
    if connection.vendor == "sqlite":
        return 1
    return max(1, requested)


class RateLimiter:
    """Shared token bucket. One per provider, safe across worker threads."""

    def __init__(self, per_second: float):
        self.min_gap = 1.0 / per_second if per_second > 0 else 0.0
        self._lock = threading.Lock()
        self._next = 0.0

    def acquire(self) -> None:
        if not self.min_gap:
            return
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.min_gap
        if wait:
            time.sleep(wait)


@dataclass
class Budget:
    """Hard caps. Exceeding one stops that cost class, not the whole run."""

    max_fetch: int = 10_000
    max_search: int = 2_000
    max_api: int = 50_000
    _used: dict = field(default_factory=lambda: {Cost.FETCH: 0, Cost.SEARCH: 0, Cost.API: 0})
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def take(self, cost: str) -> bool:
        cap = {
            Cost.FETCH: self.max_fetch,
            Cost.SEARCH: self.max_search,
            Cost.API: self.max_api,
        }.get(cost)
        if cap is None:
            return True
        with self._lock:
            if self._used[cost] >= cap:
                return False
            self._used[cost] += 1
            return True

    def report(self) -> dict:
        return dict(self._used)


@dataclass
class Context:
    """Everything a provider may need that is not the record itself."""

    http: object = None
    budget: Budget = field(default_factory=Budget)
    shared: dict = field(default_factory=dict)  # bulk indexes live here
    user_agent_email: str | None = None
    dry_run: bool = False


class Runner:
    def __init__(
        self,
        registry: Registry,
        dataset,
        ctx: Context | None = None,
        workers: int = 4,
        max_waves: int = 6,
    ):
        self.reg = registry
        self.dataset = dataset
        self.ctx = ctx or Context()
        self.workers = safe_workers(workers)
        self.max_waves = max_waves
        self._limits = {p.name: RateLimiter(p.rate_per_sec) for p in registry.all()}
        self._wlock = threading.Lock()

    # ----------------------------------------------------------------- pass --
    def run(self, only: list[str] | None = None, limit: int | None = None) -> dict:
        providers = [p for p in self.reg.all() if not only or p.name in only]

        # A provider that wants to run *after* another one needs to know whether
        # that other one is even in this pass — otherwise `--only` deadlocks it
        # waiting for something that will never run.
        active = frozenset(p.name for p in providers)
        self.ctx.shared["active_providers"] = active
        for p in providers:
            p._active_defer = getattr(p, "defer_to", frozenset()) & active

        for p in providers:  # bulk downloads / shared indexes, once each
            if getattr(p, "needs_prepare", False):
                p.prepare(self.ctx)

        recs = store.load_records(self.dataset, limit=limit)
        stats = {
            "records": len(recs),
            "claims": 0,
            "errors": 0,
            "skipped": 0,
            "by_provider": {},
        }

        def work(rec: Record):
            try:
                self._drive(rec, providers, stats)
            finally:
                connections.close_all()

        if self.workers > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as ex:
                list(ex.map(work, recs))
        else:
            for r in recs:
                work(r)

        stats["budget"] = self.ctx.budget.report()
        stats["workers"] = self.workers
        return stats

    # -------------------------------------------------------------- one row --
    def _drive(self, rec: Record, providers, stats) -> None:
        """Fire whatever is eligible, in waves, until nothing new unlocks.

        Then do it again ignoring `defer_to`. A provider that wanted to go last
        must not be starved by one that never becomes eligible for this
        particular record — `revenue_model` defers to `edgar_facts`, and most
        records are private companies EDGAR will never have anything to say
        about. Waiting costs them a wave; it must not cost them the claim.
        """
        for honor_deferrals in (True, False):
            for _ in range(self.max_waves):
                if not self._wave(rec, providers, stats, honor_deferrals):
                    break

    def _wave(self, rec: Record, providers, stats, honor_deferrals: bool) -> bool:
        """One pass over the providers. Returns whether anything fired."""
        fired = False
        for p in providers:
            if p.name in rec.ran:
                continue
            if honor_deferrals and (p._active_defer - rec.ran):
                continue
            if not p.eligible(rec):
                continue
            if not self.ctx.budget.take(p.cost):
                with self._wlock:
                    stats["skipped"] += 1
                rec.ran.add(p.name)
                continue

            self._limits[p.name].acquire()
            ts = NOW()
            try:
                claims = list(p.run(rec, self.ctx) or [])
            except Exception as e:  # isolation: one bad row must not end the run
                store.mark_run(rec.record_id, p.name, "error", f"{type(e).__name__}: {e}", ts)
                rec.ran.add(p.name)
                with self._wlock:
                    stats["errors"] += 1
                    stats["by_provider"].setdefault(p.name, {"ok": 0, "err": 0})["err"] += 1
                continue

            with transaction.atomic():
                if claims:
                    store.save_claims(rec.record_id, claims)
                    for c in claims:
                        rec.add(c)
                    # Promote claims into fields so dependent providers unlock.
                    # A verified claim always wins; an unverified one only
                    # fills a gap.
                    for c in claims:
                        if c.verified:
                            rec.fields[c.field] = c.value
                        else:
                            rec.fields.setdefault(c.field, c.value)
                    store.set_fields(rec.record_id, rec.fields)
                store.mark_run(rec.record_id, p.name, "ok" if claims else "empty", None, ts)

            rec.ran.add(p.name)
            fired = True
            with self._wlock:
                stats["claims"] += len(claims)
                d = stats["by_provider"].setdefault(p.name, {"ok": 0, "err": 0})
                d["ok"] += 1
        return fired
