"""Providers that mine the list itself, before any network call.

A list assembled from site or facility records contains the same corporate group
many times over. Collapsing those relationships costs nothing, shrinks the set
that needs enrichment, and gives every subsidiary a parent whose attributes it
can inherit. Doing this FIRST is the cheapest win available.
"""

from __future__ import annotations

from ..core.model import Claim, Evidence
from ..core.provider import BaseProvider, Cost

# Anchors too generic to imply ownership.
STOP_ANCHORS = {
    "global",
    "international",
    "industries",
    "industrial",
    "technologies",
    "technology",
    "systems",
    "solutions",
    "products",
    "group",
    "auto",
    "automotive",
    "electronics",
    "engineering",
    "manufacturing",
    "america",
    "americas",
    "europe",
    "asia",
    "national",
    "united",
    "general",
    "standard",
    "new",
    "first",
    "grupo",
    "the",
    "de",
    "compagnie",
    "societe",
}

# Place names are the dominant false positive: a facility list is full of
# "Shanghai <anything>", and a first-token match on a city invents a corporate
# group that does not exist. Learned by watching exactly that happen.
CITY_ANCHORS = {
    "shanghai",
    "beijing",
    "shenzhen",
    "guangzhou",
    "tianjin",
    "chongqing",
    "wuhan",
    "chengdu",
    "suzhou",
    "hangzhou",
    "ningbo",
    "qingdao",
    "dalian",
    "xian",
    "nanjing",
    "shenyang",
    "changchun",
    "wuxi",
    "foshan",
    "dongguan",
    "jiangsu",
    "zhejiang",
    "guangdong",
    "shandong",
    "hebei",
    "henan",
    "anhui",
    "hong",
    "kong",
    "taipei",
    "seoul",
    "busan",
    "tokyo",
    "osaka",
    "nagoya",
    "yokohama",
    "mumbai",
    "delhi",
    "chennai",
    "bangalore",
    "pune",
    "jakarta",
    "bangkok",
    "manila",
    "hanoi",
    "saigon",
    "istanbul",
    "ankara",
    "moscow",
    "warsaw",
    "prague",
    "budapest",
    "bucharest",
    "berlin",
    "munich",
    "hamburg",
    "frankfurt",
    "stuttgart",
    "paris",
    "lyon",
    "milan",
    "milano",
    "torino",
    "roma",
    "madrid",
    "barcelona",
    "lisboa",
    "london",
    "birmingham",
    "manchester",
    "dublin",
    "amsterdam",
    "rotterdam",
    "brussels",
    "zurich",
    "geneva",
    "vienna",
    "stockholm",
    "oslo",
    "helsinki",
    "copenhagen",
    "monterrey",
    "guadalajara",
    "queretaro",
    "puebla",
    "tijuana",
    "juarez",
    "saltillo",
    "toronto",
    "montreal",
    "detroit",
    "chicago",
    "houston",
    "atlanta",
    "dallas",
    "phoenix",
    "seattle",
    "boston",
    "sao",
    "paulo",
    "rio",
    "campinas",
    "curitiba",
    "manaus",
    "bogota",
    "santiago",
    "lima",
    "cairo",
    "casablanca",
    "johannesburg",
    "dubai",
}


class SelfLink(BaseProvider):
    """Link subsidiaries to a parent already present in the list.

    Bulk provider: prepare() builds the anchor index once across every record,
    then run() is a dictionary lookup per row.
    """

    name = "selflink"
    requires = frozenset({"clean_name"})
    provides = frozenset({"parent_name", "parent_record_id"})
    cost = Cost.BULK
    needs_prepare = True
    min_anchor_len = 4
    # A company must look substantial to anchor a group.
    anchor_min_sites = 5
    anchor_min_countries = 3

    def __init__(self):
        self.anchors: dict[str, tuple[int, str]] = {}

    def prepare(self, ctx) -> None:
        from warehouse.models import EnrichmentRecord

        dataset = (ctx.shared or {}).get("dataset")
        qs = EnrichmentRecord.objects.all()
        if dataset is not None:
            qs = qs.filter(dataset=dataset)

        geo = set(CITY_ANCHORS)
        cand: dict[str, list] = {}
        for pk, source_key, fields in qs.values_list("pk", "source_key", "fields"):
            f = fields or {}
            # Country names in THIS list become banned anchors too: a list of
            # Thai plants makes "thailand" look like a corporate group.
            for tok in str(f.get("country") or "").lower().replace("-", " ").split():
                if len(tok) > 2:
                    geo.add(tok)
            try:
                sites = int(f.get("n_sites") or 0)
                ctry = int(f.get("n_countries") or 0)
            except (TypeError, ValueError):
                sites = ctry = 0
            if sites < self.anchor_min_sites and ctry < self.anchor_min_countries:
                continue
            toks = (f.get("clean_name") or "").split()
            if not toks:
                continue
            a = toks[0]
            if len(a) >= self.min_anchor_len:
                cand.setdefault(a, []).append((pk, source_key))

        banned = STOP_ANCHORS | geo
        # An anchor claimed by two different large companies is ambiguous; drop it.
        self.anchors = {a: v[0] for a, v in cand.items() if a not in banned and len(v) == 1}
        ctx.shared["selflink_anchors"] = len(self.anchors)

    def run(self, rec, ctx):
        toks = (rec.get("clean_name") or "").split()
        if not toks:
            return
        hit = self.anchors.get(toks[0])
        if not hit or hit[0] == rec.record_id:
            return
        pid, pname = hit
        ev = Evidence(
            locator=f"intralist_anchor:{toks[0]}", snippet=f"shares leading token with {pname}"
        )
        # 0.75: a strong hint from name structure, not a registry-confirmed fact.
        yield Claim("parent_name", pname, 0.75, self.name, ev)
        yield Claim("parent_record_id", pid, 0.75, self.name, ev)
