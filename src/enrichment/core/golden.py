"""Turn many competing claims into one defensible value per field.

Precedence beats confidence. A provider's self-reported confidence is a guess
about its own output; source precedence is a judgement about the source itself,
and it is the more reliable of the two. A company's own website naming itself
outranks a search snippet even when the snippet's scorer felt good about it.

Every resolution records how many rivals it beat and whether the call was close,
so `contested=1` gives you a review queue instead of a false sense of accuracy.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

# Higher wins. Registry/filing data first, then the company itself, then
# third-party descriptions, then anything inferred locally.
PRECEDENCE = {
    # Registries and regulatory filings: someone is legally accountable for these.
    "gleif": 100,
    "gleif_api": 100,
    "companies_house": 95,
    "edgar_facts": 96,  # XBRL a company filed about itself, under oath
    "edgar_submissions": 94,  # SEC's entity record for that filer
    "edgar_issuer": 90,  # SEC's own ticker/CIK/name catalogue
    "fred": 85,  # official statistics; macro context, not entity data
    # Offline derivations from committed reference tables.
    "geo": 82,
    "jurisdiction": 82,
    "geo_subdivision": 82,
    # The company's own website.
    "site_jsonld": 80,
    "site_probe": 75,
    "rdap": 70,
    "wikidata": 60,
    "wikipedia": 55,
    "web_search": 40,
    "source_csv": 30,
    "selflink": 25,
    "domain_guess": 20,
    # Inference, last. hq_inference reads a registration fact; revenue_model is
    # a benchmark multiplication. Neither may ever outrank a filing.
    "hq_inference": 18,
    "revenue_model": 10,
    "model": 10,
}
DEFAULT_PRECEDENCE = 15

# Fields where several values are legitimate simultaneously; keep them all.
MULTI_VALUED = {
    "vertical",
    "industry",
    "naics",
    "sameAs",
    "reference",
    "alias",
    "trade_name",
    "website_candidate",
    "phone",
    # Every reason a record was flagged matters; keeping only the
    # top-ranked one turned a review queue into a single sentence.
    "validation_reason",
    # A record sits in more than one macro context at once.
    "macro_series",
    "macro_bundle",
    "exchange",
}


def _rank(c) -> tuple:
    return (int(c.verified), PRECEDENCE.get(c.provider, DEFAULT_PRECEDENCE), round(c.confidence, 4))


def resolve_record(rec) -> dict[str, dict]:
    """{field: {value, confidence, provider, ev_url, rivals, contested}}"""
    by_field = defaultdict(list)
    for c in rec.claims:
        by_field[c.field].append(c)

    out = {}
    for fld, claims in by_field.items():
        if fld in MULTI_VALUED:
            # Union of distinct values; confidence = best seen for that value.
            best: dict[str, Any] = {}
            for c in claims:
                k = json.dumps(c.value, sort_keys=True, default=str)
                if k not in best or _rank(c) > _rank(best[k]):
                    best[k] = c
            winners = sorted(best.values(), key=_rank, reverse=True)
            out[fld] = {
                "value": [w.value for w in winners],
                "confidence": max(w.confidence for w in winners),
                "provider": ",".join(sorted({w.provider for w in winners})),
                "ev_url": winners[0].evidence.url,
                "rivals": 0,
                "contested": 0,
            }
            continue

        ranked = sorted(claims, key=_rank, reverse=True)
        top = ranked[0]
        distinct = {json.dumps(c.value, sort_keys=True, default=str) for c in claims}
        rivals = len(distinct) - 1

        # Contested = a different value came within one precedence tier and
        # 0.1 confidence of the winner. Those are the rows worth a human minute.
        contested = 0
        for c in ranked[1:]:
            if c.value == top.value:
                continue
            same_tier = (
                abs(
                    PRECEDENCE.get(c.provider, DEFAULT_PRECEDENCE)
                    - PRECEDENCE.get(top.provider, DEFAULT_PRECEDENCE)
                )
                <= 20
            )
            if same_tier and (top.confidence - c.confidence) < 0.10:
                contested = 1
            break

        out[fld] = {
            "value": top.value,
            "confidence": top.confidence,
            "provider": top.provider,
            "ev_url": top.evidence.url,
            "rivals": rivals,
            "contested": contested,
        }
    return out


def write_golden(record_id: int, rec) -> int:
    """Replace a record's golden fields from its current claims. Returns the count."""
    from django.db import transaction

    from warehouse.models import EnrichmentGoldenField

    res = resolve_record(rec)
    rows = [
        EnrichmentGoldenField(
            record_id=record_id,
            field=fld[:64],
            value=d["value"],
            confidence=d["confidence"],
            provider=d["provider"][:128],
            ev_url=(d["ev_url"] or "")[:1024],
            rivals=d["rivals"],
            contested=bool(d["contested"]),
        )
        for fld, d in res.items()
    ]
    with transaction.atomic():
        EnrichmentGoldenField.objects.filter(record_id=record_id).delete()
        EnrichmentGoldenField.objects.bulk_create(rows)
    return len(rows)
