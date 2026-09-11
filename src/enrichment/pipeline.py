"""Default provider wiring. Import, extend, or replace wholesale.

The registry sorts providers cheapest-first, so the order below is descriptive
rather than prescriptive: free inference always runs before anything touches the
network, and the network providers only fire on the rows the free ones could not
finish. ``manage.py enrich_plan`` prints the wave order the runner derives.
"""

from __future__ import annotations

from .core.provider import Registry
from .providers.edgar import EdgarFacts, EdgarIssuerMatch, EdgarSubmissions
from .providers.estimate import RevenueModel
from .providers.fred import FredDeflator, FredMacroContext
from .providers.geo import Geocode, GeoNormalize, SubdivisionResolve
from .providers.intralist import SelfLink
from .providers.registry import HqInference, JurisdictionCheck
from .providers.webdiscovery import DomainCandidates, SearchDiscovery, SiteProbe


def default_registry(
    *,
    enable_search: bool = False,
    enable_web: bool = True,
    enable_geocode: bool = False,
) -> Registry:
    """The standard graph.

    The switches gate *network* providers only, so an offline run still produces
    everything that can be derived without one. ``enable_search`` is off by
    default because it needs an external search backend and is the most expensive
    thing here. ``enable_geocode`` is off because the public Nominatim instance
    asks for 1 req/s and a real contact address — point ``ctx.shared['nominatim']``
    at your own before turning it on.
    """
    reg = Registry()

    # Free, offline, total coverage.
    reg.register(GeoNormalize())
    reg.register(SubdivisionResolve())
    reg.register(JurisdictionCheck())
    reg.register(HqInference())
    reg.register(FredMacroContext())
    reg.register(FredDeflator())
    reg.register(RevenueModel())

    # Domain guessing is pure string work — it proposes candidates and makes no
    # requests — so it belongs with the offline providers, not behind the web
    # switch. Gating it on `enable_web` meant `--no-web --only domain_guess`
    # silently did nothing at all, which is the worst way for a flag to be wrong:
    # the run reports success and produces no claims.
    reg.register(DomainCandidates())

    # Bulk: one shared index built once, then a dictionary lookup per record.
    reg.register(SelfLink())
    reg.register(EdgarIssuerMatch())

    # Database-first SEC reads; only fire on rows that resolved to a CIK.
    reg.register(EdgarSubmissions())
    reg.register(EdgarFacts())

    # The network half.
    if enable_web:
        reg.register(SiteProbe())
    if enable_search:
        reg.register(SearchDiscovery())
    if enable_geocode:
        reg.register(Geocode())
    return reg
