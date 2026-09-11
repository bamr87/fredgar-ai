---
title: "Providers Propose, Resolution Disposes: Building an Enrichment Framework"
date: 2026-09-10
categories: [data-engineering, architecture, ai-assisted-development]
tags: [mdm, entity-resolution, schema-org, web-scraping, master-data, python]
excerpt: "Turning a list of 10,982 company names into vendor master data — and why the one rule that made it work was forbidding providers from writing anything."
---

## The problem with enrichment scripts

Every enrichment script starts the same way. Loop over the list, call a source, write the answer into a column. It works for one source. At three sources you have a column that four different code paths can write to, and no way to answer the only question that matters in production:

> Where did this value come from, and what disagreed with it?

I had 10,982 manufacturing company names and a goal of customer/vendor master data. The interesting design work was not finding sources. It was building something where that question always has an answer.

## The one rule

**Providers never write to a record. They emit claims.**

```python
@dataclass(frozen=True)
class Claim:
    field: str          # 'website' | 'legal_name' | 'employees'
    value: Any
    confidence: float   # the provider's honest estimate of its own output
    provider: str
    evidence: Evidence  # url + snippet + locator + retrieved_at
    verified: bool      # did we CHECK this, or merely propose it?
```

Resolution happens later, once, in one place. Everything good downstream falls out of that single constraint:

- **Auditability** is free. `evidence --name "Eaton"` prints every claim, its
  confidence, and the URL that supports it.
- **Conflict becomes data.** Two comparable sources disagreeing marks the field
  `contested=1` — a review queue instead of a silent coin flip.
- **Re-running one source** after fixing a bug loses nothing the others found.

That last one sounds minor until the fourth time you fix a parser and have to decide whether to rebuild everything.

## What makes it a framework

A provider declares what it **needs** and what it **yields**:

```python
class SiteProbe(BaseProvider):
    name = "site_probe"
    requires = frozenset({"website_candidate"})
    provides = frozenset({"website", "legal_name", "phone", "sameAs"})
    cost = Cost.FETCH
    rate_per_sec = 3.0
```

The runner reads those declarations and derives the execution order itself:

```
wave 1: domain_guess   cost=free    needs=['name']              -> ['website_candidate']
        site_probe     cost=fetch   needs=['website_candidate'] -> ['website','legal_name',...]
        web_search     cost=search  needs=['name']              -> ['reference','website_candidate']
```

Adding Companies House means writing one class. The orchestrator never changes. And because providers are sorted cheapest-first, free inference always runs before anything touches the network — search only fires on records where the free path already failed. In my end-to-end run, search was skipped for 100% of records that had already verified a domain.

## Resolution: precedence beats confidence

Confidence is a provider's guess about its own output. Precedence is a judgement about the source itself, and it is the more reliable of the two.

```python
PRECEDENCE = {
    "gleif": 100, "edgar": 95,        # registries and filings
    "site_jsonld": 80, "site_probe": 75,
    "wikidata": 60,
    "web_search": 40,
    "domain_guess": 20, "model": 10,  # inference, last
}
```

Ranked by `(verified, precedence, confidence)`. A verified domain at 0.70 beats a guessed one at 0.90 — which is exactly right, and exactly what a naive `max(confidence)` gets wrong.

## Website discovery is the linchpin

Once you have a company's own domain, almost everything becomes reachable: legal name, address, phone, founding date, headcount, and `sameAs` links to every other public reference. schema.org `Organization` markup does a lot of this work for you — when a site publishes it, one fetch yields a dozen attributes with a citable URL.

Which is why **an unverified domain is worse than no domain.** Every attribute harvested from the wrong site inherits the error, silently, with a plausible evidence URL attached.

## The bug that justified the whole design

My first verifier scored a candidate domain on name signals with what looked like a reasonable prefix test:

```python
if ratio >= 0.6 or clean(value).startswith(want) or want.startswith(clean(value)):
    score += weight
```

Then I ran it against a fixture of **Eaton Vance** — an investment manager — while looking for **Eaton Corporation**, a power management manufacturer.

```
Eaton Corporation plc   VERIFY   0.99   jsonld_legal_name~1.00, og_site_name~1.00, domain_echo
```

`"eaton vance".startswith("eaton")` is `True`. The two companies share nothing but a word, and my verifier was 99% confident. Every attribute on that page — headquarters, phone, employee count, industry — would have flowed into the master record with a citable URL pointing at the wrong company.

The fix required three separate rules, because each one alone is defeatable:

**1. Extra distinctive tokens are a disqualification, not a missing signal.**

```python
distinctive_extra = {t for t in (B - A) if t not in DESCRIPTORS and len(t) > 2}
if distinctive_extra:
    return 0.25, f"distinctive_extra={distinctive_extra}"
```

If a site states its own identity and it is not yours, that is positive evidence against, not merely absent evidence for. `vance` disqualifies. So does `capital` in `Lear Capital` vs `Lear Corporation` — which I only caught because I'd carelessly put "capital" in my generic-descriptor list and the test caught it.

**2. Titles are matched on coverage, never symmetrically.** Page titles carry taglines — `"Gibbens Industries Pty Ltd - Automotive Components"` — so extra tokens are expected and must not be penalised. Instead, demand that *every* token of the company name appears.

**3. Single-token names can never be carried by a title.** `Eaton` honestly appears in the titles of several unrelated firms. Names that clean down to one token require an exact domain echo before anything trusts them.

Six adversarial fixtures now guard this: a real site, a `@graph`-nested one, a site with no structured data, a parked domain, an aggregator profile, and the wrong company. All six pass. They are the first thing I run.

## Testing enrichment without a network

The environment I was working in blocked outbound HTTP entirely. That turned out to improve the design rather than block it.

The interesting logic in an enrichment pipeline is not the happy path. It is what happens when a fetch **fails**, when a domain is **parked**, when a site belongs to **somebody else**. Those paths are hard to exercise reliably against the live web — you cannot summon a parked domain on demand — and trivial to exercise against fixtures.

```python
class MockHttp:
    """Serves fixtures by domain; everything else raises, like a dead domain."""
    def get(self, url, **kw):
        fx = self.routes.get(registrable_domain(url))
        if not fx:
            raise ConnectionError(f"NXDOMAIN {registrable_domain(url)}")
        return (self.dir / fx).read_bytes()
```

Running the real framework over the real 10,982-row list with this mock proved the parts that actually matter: error isolation (a provider raising on one record kept that record's other claims), checkpoint resumption (a second run produced zero duplicate claims), budget enforcement (5 records, `max_fetch=2` → 2 fetched, 3 skipped, cap held), and correct fallback ordering.

## What master data actually needs

The export carries the resolved record plus the columns that decide whether you can trust it:

| Column | Why |
|---|---|
| `completeness` | Weighted by what a vendor master is *for* — paying the right entity, classifying spend, rolling up to a parent |
| `contested_fields` | Where comparable sources disagreed |
| `unverified_website` | The most dangerous cell in the file, because it looks exactly like a good one |
| `references` | Every public source found for this party |
| `revenue_basis` | `reported` vs `estimated`, never blended |

Master data is judged on trustworthiness, not row count. A record you cannot audit is not master data; it is a spreadsheet with ambitions.

## Working with AI on this

**Adversarial fixtures beat happy-path fixtures, by a lot.** The Eaton Vance case is the entire reason this framework is trustworthy, and it existed only because I asked for fixtures designed to *break* the matcher rather than demonstrate it. Ask for the cases that should fail.

**Interrogate green results.** An earlier version of my decoy test passed 5/5 and I nearly moved on. Checking *why* revealed the decoys had landed in different blocking keys and never reached the scoring logic at all — the rule I thought I'd tested was completely unexercised. A passing test you have not explained is not evidence.

**Let the tool audit its own rejects.** The single highest-value command of this project was a five-line histogram of the most common tokens among *discarded* rows. It surfaced an entire class of missing legal forms — Mexican `de C.V.`, Brazilian `Ltda`, Malaysian `Sdn Bhd`, Indonesian `PT` — real companies my Anglo-European suffix list had silently thrown away. Audit what your filter rejects, not what it accepts. The rejects are where the bias lives.

**Constraints are design pressure.** No network access forced a mock layer that made the failure paths testable. I would not have written it otherwise, and the framework is better for it.

---

*The framework is zero-dependency Python — standard library only, SQLite for state. Providers propose, resolution disposes.*
