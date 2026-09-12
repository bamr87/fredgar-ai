"""Offline HTTP and search doubles for the web-discovery providers.

These exist so the framework's behaviour is testable without network access,
which matters more than it sounds: the interesting logic in an enrichment
pipeline is not the happy path. It is what happens when a fetch **fails**, when
a domain is **parked**, and when a site belongs to **somebody else**. You cannot
summon a parked domain on demand, so those paths are nearly untestable against
the live web and trivial to test here.
"""

from __future__ import annotations

import pathlib

from enrichment.providers.webdiscovery import registrable_domain

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class MockHttp:
    """Serves fixtures by domain; everything else raises, like a dead domain."""

    def __init__(self, routes: dict[str, str], fixtures_dir: pathlib.Path = FIXTURES):
        self.routes = routes  # registrable domain -> fixture filename
        self.dir = fixtures_dir
        self.calls: list[str] = []

    def get(self, url: str, accept: str = "text/html", **kwargs) -> bytes:
        self.calls.append(url)
        fixture = self.routes.get(registrable_domain(url))
        if not fixture:
            raise ConnectionError(f"NXDOMAIN {registrable_domain(url)}")
        return (self.dir / fixture).read_bytes()


class MockSearch:
    """Callable matching the ``SearchDiscovery`` backend contract."""

    def __init__(self, results: dict[str, list[dict]]):
        self.results = results
        self.queries: list[str] = []

    def __call__(self, query: str, n: int = 8) -> list[dict]:
        self.queries.append(query)
        for key, hits in self.results.items():
            if key.lower() in query.lower():
                return hits[:n]
        return []
