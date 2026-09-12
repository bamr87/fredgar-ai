# Enrichment — providers propose, resolution disposes

Takes any list of organization names and iterates it through public sources — SEC EDGAR first, then FRED macro context, business registries, geography, and the open web — to produce an auditable customer/vendor master.

```
your list ──► adapter ──► [ provider graph ] ──► claims + evidence ──► golden record ──► MDM export
                                                                            │
                                                                            └──► warehouse Company
```

Code lives in [`src/enrichment/`](../src/enrichment/) (no models of its own, like `sec_edgar`); the models are `Enrichment*` in [`warehouse/models.py`](../src/warehouse/models.py).

## The one rule

**A provider never writes to a record. It emits claims.**

```python
@dataclass(frozen=True)
class Claim:
    field: str          # 'website' | 'cik' | 'revenue_reported'
    value: Any
    confidence: float   # the provider's honest estimate of its own output
    provider: str
    evidence: Evidence  # url + snippet + locator + retrieved_at
    verified: bool      # did we CHECK this, or merely propose it?
```

Resolution happens later, once, in [`core/golden.py`](../src/enrichment/core/golden.py). Everything useful downstream falls out of that single constraint:

- **"Why does it say that?"** always has an answer — `manage.py enrich_evidence --name X` prints every claim with its source URL, and `GET /api/v1/enrichment-records/{id}/evidence/` returns the same thing.
- **Conflicting sources become data, not bugs.** A field where two comparable sources disagree is marked `contested` — a review queue instead of a coin flip.
- **Re-running one source** after fixing a bug loses nothing the others found (`enrich_run --refresh <provider>`).

## Commands

All run from `src/`.

```bash
python manage.py enrich_init --dataset manufacturing --csv ../data/list.csv --mapping manufacturing_v1
python manage.py enrich_plan --dataset manufacturing          # what WOULD run, before spending anything
python manage.py enrich_run  --dataset manufacturing --no-web # free + database-first providers
python manage.py enrich_run  --dataset manufacturing --limit 400 --max-fetch 700  # add the web half
python manage.py enrich_resolve --dataset manufacturing       # claims -> golden record
python manage.py enrich_link    --dataset manufacturing       # golden CIK -> warehouse Company
python manage.py enrich_export  --dataset manufacturing --out ../data/enrichment/vendor_master.csv
python manage.py enrich_report  --dataset manufacturing
python manage.py enrich_evidence --dataset manufacturing --name "Eaton Corporation"
```

`enrich_run` is **resumable**: every `(record, provider)` attempt is checkpointed, so re-running only does what has not been done. To genuinely re-run one provider, `--refresh edgar_facts` drops that provider's claims and checkpoints first and leaves every other provider's findings untouched.

## Providers

| Provider | Cost | Needs | Yields |
|---|---|---|---|
| `geo` | free | — | ISO-3166 frame: iso2/iso3, UN region, centroid, currency, EU/OECD |
| `geo_subdivision` | free | `geo_iso2`, `hq_region_raw` | ISO 3166-2 subdivision |
| `jurisdiction` | free | — | legal form vs country check, and **which register to query** |
| `hq_inference` | free | `countries_iso`, `legal_form_token` | HQ implied by legal form (never verified) |
| `selflink` | bulk | `clean_name` | parent/subsidiary edges within the list |
| **`edgar_issuer`** | bulk | `blocking_key` | **CIK, ticker, legal name** — from cached `ListedIssuer`, no network |
| **`edgar_submissions`** | api | `cik` | SIC, business address, phone, EIN, exchanges, former names |
| **`edgar_facts`** | api | `cik` | **reported** revenue, employees, net income, total assets |
| **`fred`** | free | — | macro bundle + series governing the record's sector |
| **`fred_deflator`** | free | `revenue_reported`, `revenue_period_end` | revenue restated in constant dollars |
| `revenue_model` | free | — | modelled revenue, benchmarked against the list's own filers |
| `domain_guess` | free | — | website candidates (hypotheses) |
| `site_probe` | fetch | `website_candidate` | **verified** website, legal name, phone, HQ city, `sameAs` |
| `web_search` | search | — | candidates + references (needs a search backend) |

### SEC EDGAR

`edgar_issuer` blocks the input list against `ListedIssuer` — SEC's own `company_tickers.json`, already cached in the warehouse — so finding each row's CIK is a dictionary lookup, not a request. Running it first means the API providers only fire on rows that are actually filers; on a supplier list that is a small minority.

Both API providers read through [`sec_edgar.services.edgar_sec_payload`](../src/sec_edgar/services/edgar_sec_payload.py), so a payload already in the database is reused and SEC is never called twice for the same entity. That is not an optimisation — SEC enforces fair-access limits, and a run over ten thousand names is exactly the traffic shape they throttle.

**Identity gates everything.** Nothing the SEC providers emit can be better established than the CIK it came from: on an unverified CIK, every claim is written `verified=False` with its confidence scaled down and a `validation_reason` recorded. Stamping XBRL "verified" because a filer signed it is only true if it is the *right* filer.

### FRED

`fred` links each record to the series that govern its sector, using the `industries` tags already curated in [`public_data/bundles/`](../src/public_data/bundles/). Sector comes from SEC's SIC code where one exists, because SIC is what a registrant told SEC it *does*, whereas a supplier list's verticals describe who it sells to.

FRED measures the United States, so every macro claim carries an explicit `macro_scope`: `domestic_us`, or `us_proxy` at much lower confidence. Attaching US industrial production to a Malaysian supplier without saying so would be the macro equivalent of an unverified website.

`fred_deflator` is the EDGAR↔FRED join: it takes a reported revenue and the fiscal period it belongs to, and restates it in current dollars using a sector PPI (or headline CPI when nothing sector-specific fits). Ranking vendor spend by nominal figures across different fiscal years ranks it wrong.

**It reads observations from the warehouse only and never fetches.** With no FRED observations synced it emits nothing at all — a deflator guessed from a neighbouring year is a rounding error with provenance. Sync them first:

```bash
python manage.py sync_series_bundle --slug manufacturing   # needs FRED_API_KEY
```

### Revenue model

The original framework hard-coded revenue-per-employee with, in its own words, "order-of-magnitude placeholders". This version derives the benchmark from the filers in the list itself: `edgar_facts` supplies reported revenue and headcount for every SEC registrant among the records, and the median ratio within a SIC group becomes the benchmark for the private companies in that same group.

The sample size travels with every estimate (`tier=sic4|sic2|all_filers|fallback`, `n=…` in `revenue_method`), so a reader can see that a group of six filers is thinner evidence than a group of sixty. Estimates are never verified and never blended with reported figures — `revenue_basis` keeps them apart.

Because the benchmark is built from claims, a *first* run has nothing to learn from. The sequence is:

```bash
python manage.py enrich_run --dataset X --no-web                    # EDGAR pass
python manage.py enrich_run --dataset X --no-web --refresh revenue_model  # now benchmarked
```

## Resolution: precedence beats confidence

Confidence is a provider's guess about its own output. Precedence is a judgement about the source, and it is the more reliable of the two.

```python
PRECEDENCE = {
    "gleif": 100, "edgar_facts": 96, "companies_house": 95,
    "edgar_submissions": 94, "edgar_issuer": 90, "fred": 85,
    "geo": 82, "jurisdiction": 82,
    "site_jsonld": 80, "site_probe": 75,
    "web_search": 40, "source_csv": 30,
    "hq_inference": 18, "revenue_model": 10,
}
```

Ranked by `(verified, precedence, confidence)`. A verified filing at 0.70 beats a guess at 0.95 — which is exactly right, and exactly what `max(confidence)` gets wrong.

`contested=1` marks a field where a *comparable* source (within 20 precedence points and 0.10 confidence) proposed a different value. Eaton is the live example: SEC gives Dublin, where the plc is domiciled; its website gives Beachwood, where the business is run. Both are true, precedence picks SEC, and `contested` says *look*.

## Scheduling: `requires` vs `defer_to`

`requires` is about fields a provider **cannot run without** — it determines the wave order. `defer_to` is about fields that would **change its answer** if they arrived. The distinction exists because the runner fires providers cheapest-first *within* a wave, so a free provider reading a field an API provider supplies would otherwise run too early and answer from the seed.

Deferral is a preference, not a precondition: the runner drops it once a record has gone quiet. A private company still gets a modelled revenue — it gets it after EDGAR has confirmed there is nothing to report.

## Reading the export

| Column | Why it exists |
|---|---|
| `hard_completeness` | Completeness excluding modelled values. **The number to trust** |
| `validation_status` | Derived verdict: `registry_validated` > `sec_registrant` > `jurisdiction_consistent` > `geo_only` > `unchecked` |
| `contested_fields` | Where comparable sources disagreed. Your review queue |
| `unverified_website` | The most dangerous cell in the file, because it looks exactly like a good one |
| `revenue_basis` | `reported` vs `estimated`, never blended |
| `revenue_method` | The benchmark, its tier and its sample size, for every estimate |
| `macro_scope` | `domestic_us` or `us_proxy` — whether FRED measures this jurisdiction |
| `validation_reasons` | Every reason a record was flagged, pipe-separated |

## Website discovery: the linchpin, and the danger

Once a company's own domain is known, nearly everything else is reachable. So domain resolution runs cheapest-first — `domain_guess` (free), then `site_probe` (fetch), then `web_search` (search, only where nothing verified).

**An unverified domain is worse than no domain**, because every attribute harvested from it inherits the error silently. `verify_site` scores independent signals and applies three hard rules:

- **A site stating an identity that is not yours is a disqualification**, not a missing signal. `Eaton` vs `Eaton Vance`, `Lear Corporation` vs `Lear Capital`.
- **Titles carry taglines**, so they match on coverage, never symmetrically — and a single-token name can never be carried by a title alone.
- **Single-token names** demand an exact domain echo, because they honestly match several unrelated firms.

The same reasoning guards `edgar_issuer`, structurally: blocking on the sorted token set means a name carrying an extra distinctive token lands in a different block and is never a candidate at all.

Six adversarial fixtures guard this in [`tests/enrichment/test_verify.py`](../tests/enrichment/fixtures/): a real site, a `@graph`-nested one, a site with no structured data, a parked domain, an aggregator profile, and the wrong company.

## API

Read-only. Running providers spends SEC and search budget and takes minutes, so it belongs to `manage.py` (and Celery), not to a request a browser can retry.

| Route | Returns |
|---|---|
| `GET /api/v1/enrichment-datasets/` | datasets with record counts |
| `GET /api/v1/enrichment-datasets/{slug}/report/` | coverage, validation tiers, per-provider outcomes |
| `GET /api/v1/enrichment-records/?dataset__slug=X` | enriched records with resolved values |
| `GET /api/v1/enrichment-records/{id}/evidence/` | every claim, provider, confidence and source URL |
| `GET /api/v1/enrichment-records/contested/` | the review queue |

## Adding a source

One class, and the orchestrator never changes:

```python
class CompaniesHouse(BaseProvider):
    name = "companies_house"
    requires = frozenset({"geo_iso2"})
    provides = frozenset({"registration_number", "entity_status", "hq_postal"})
    cost = Cost.API
    rate_per_sec = 5.0

    def eligible(self, rec):
        return rec.get("geo_iso2") == "GB" and super().eligible(rec)

    def run(self, rec, ctx):
        yield Claim("registration_number", ..., 0.95, self.name, Evidence(url=...), verified=True)
```

Register it in [`pipeline.py`](../src/enrichment/pipeline.py) and `enrich_plan` immediately shows where it lands in the wave order. Every record already carries `registry_name`, `registry_url`, `registry_ra` and `registry_free_api`, so the offline `jurisdiction` provider has already told you which register to write next.
