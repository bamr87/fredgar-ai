# API and CLI

The REST API and management commands for **Fredgar AI** (FRED + EDGAR, with AI) — the backend serving SEC EDGAR company data and FRED macro series with AI-assisted analysis.

All paths below are relative to the API host (e.g. `http://127.0.0.1:8000`). Authenticated vs anonymous behavior follows DRF defaults in settings; many endpoints are open for local development.

## REST API

**Versioned base:** `/api/v1/`  
**Legacy alias:** `/api/` (same routes).

### Health and reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health/` | Liveness. |
| GET | `/api/v1/health/ready/` | Readiness; checks database connectivity. |
| GET | `/api/v1/reference/sic-codes/` | SIC lookup/autocomplete (`q`, `code`, `limit`). |

### Router resources

Registered with `DefaultRouter` (list/create/detail patterns apply where the viewset allows writes):

| Prefix | ViewSet | Notes |
|--------|---------|--------|
| `/companies/` | `CompanyViewSet` | Filter: `ticker`, `cik`, `industry`, `sic_code`, `hq_state`. Search on name/ticker/cik. |
| `/company-metadata/` | `CompanyMetadataViewSet` | Read-only, paginated metadata + filters for dashboards. |
| `/filings/` | `FilingViewSet` | Filing CRUD + custom actions below. |
| `/facts/` | `FactViewSet` | XBRL facts; supports filtering via `FactFilterSet`. |
| `/sections/`, `/tables/` | Section/table CRUD | Linked to filings. |
| `/derived-metrics/` | Read-only | Computed metrics. |
| `/peer-groups/` | `PeerGroupViewSet` | Peer sets + analytics action. |
| `/public-series/` | Read-only | External series catalog. |
| `/public-observations/` | Read-only | Series observations. |
| `/series-bundles/` | `SeriesBundleViewSet` | Bundles by `slug`; nested observations action. |

### Custom actions (`companies`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/companies/edgar-search/?q=&limit=&force_refresh=` | Search `ListedIssuer` directory; optional refresh from SEC. |
| POST | `/api/v1/companies/from-edgar/` | Body: `ticker`, `cik`, optional `name` — get or create `Company`. |
| POST | `/api/v1/companies/bulk-from-edgar-tickers/` | Bulk insert/update from SEC ticker file. |
| POST | `/api/v1/companies/{id}/suggest-schema/` | Heuristic JSON schema hints (placeholder for richer filing-driven logic). |
| POST | `/api/v1/companies/{id}/sync-submissions/` | Sync filing index from SEC. |
| POST | `/api/v1/companies/{id}/sync-facts/` | Sync companyfacts into `Fact`. |
| GET | `/api/v1/companies/{id}/edgar-sync-status/` | Last sync timestamps and error snippet. |
| GET | `/api/v1/companies/{id}/analytics/latest-by-concepts/?concepts=&taxonomy=` | Latest fact per concept. |
| GET | `/api/v1/companies/{id}/analytics/timeseries/?concept=&taxonomy=&limit=` | Time series for one concept. |
| GET | `/api/v1/companies/{id}/statements/?statement_type=&taxonomy=` | Curated statement view (balance/income/cash-flow) from Facts. |
| POST | `/api/v1/companies/{id}/compute-metrics/` | Compute/refresh `DerivedMetric` rows from Facts (admin only). |
| GET | `/api/v1/companies/{id}/profile/` | Consolidated Company-360 view (identity, financials, filings, documents, CRM) with provenance. |
| GET | `/api/v1/companies/{id}/leadership/` | Officers/directors/owners extracted from SEC Forms 3/4/5 (titles, roles, tenure, insider shares). |
| GET | `/api/v1/companies/{id}/stakeholder-assessment/` | Transparent people-vs-profits orientation index + decomposed signals + caveats. See [leadership-methodology.md](leadership-methodology.md). |
| POST | `/api/v1/companies/{id}/analyze-leadership/` | Run the gated LLM narrative analysis (initiatives/quotes/direction), grounded in SEC filing text (admin only; off unless `ENABLE_AI_ANALYSIS`). |
| GET | `/api/v1/companies/{id}/leadership-analysis/` | Latest stored LLM leadership analysis (summary, initiatives, verbatim quotes, cited sources, caveats). |
| GET | `/api/v1/companies/compare/?group_by=&concept=` | Cohort compare of a concept across an industry/region group. |
| GET | `/api/v1/companies/leadership-compare/?cik=&cik=` | Compare leadership footprint + stakeholder orientation across companies. |

### Other custom actions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/company-metadata/facets/` | Aggregates: SIC, state, industry, coverage counts. |
| POST | `/api/v1/filings/ingest-htm/` | Body: `url`, and `ticker` or `cik` — ingest one HTM filing. |
| POST | `/api/v1/filings/ingest-submission/` | Body: `url`, and `ticker` or `cik` — decompose a full submission `.txt` into `FilingDocument` rows (admin). |
| GET | `/api/v1/filings/search/?q=&form_type=&cik=` | Full-text search across ingested filing-document text (Postgres FTS; SQLite substring fallback). |
| GET | `/api/v1/tasks/{task_id}/` | Celery task state for an async sync job. |
| GET | `/api/v1/facts/facets/?company=` | Per-company fact aggregates (taxonomy, top concepts, years). |
| GET | `/api/v1/peer-groups/{id}/analytics/peer-fact-compare/?concept=&taxonomy=` | Compare concept across peer group. |
| GET | `/api/v1/series-bundles/{slug}/observations/?limit=` | Bundle observations snapshot. |

Interactive exploration: open `/api/v1/` in a browser with Django staff session if browsable API is enabled.

**OpenAPI:** Served by `drf-spectacular` at `/api/v1/schema/` (OpenAPI 3, titled "Fredgar AI API") with Swagger UI at `/api/v1/docs/`. This document remains a human-readable route inventory.

---

## Management commands

Run from `src/` with `PYTHONPATH=src` and `DJANGO_SETTINGS_MODULE=config.settings` (or `cd src` after `pip install`):

```bash
cd src
python manage.py <command> [options]
```

### `sec_edgar`

| Command | Purpose |
|---------|---------|
| `ingest_htm` | Ingest one HTM filing (`--url`, optional `--ticker` / `--cik`). |
| `ingest_submission` | Decompose a full submission `.txt` into `FilingDocument` rows (`--url`, `--ticker`/`--cik`, `--no-extract`). |
| `sync_submissions` | Pull SEC submissions index into `Filing` for a company (`--ticker` / `--cik`). |
| `sync_company_facts` | Load companyfacts into `Fact` (`--ticker` / `--cik`). |
| `sync_listed_issuers` | Refresh `ListedIssuer` from `company_tickers.json`. |
| `bulk_load_edgar_companies` | Upsert `Company` rows from SEC ticker JSON. |
| `bulk_load_edgar_zip` | Load nightly `submissions.zip` / `companyfacts.zip` (heavy). |
| `sync_sic_reference` | Fetch/cache SIC reference JSON under data dir. |
| `sync_accounting_reference` | Merge `data/reference/sources/accounting/` (`acct_facts.csv` + `acct_facts_overlay.json`) into `generated/us_gaap_account_map.json`. |
| `generate_edgar_reference` | Regenerate portions of `data/reference/` from live SEC samples. |

### `warehouse`

| Command | Purpose |
|---------|---------|
| `populate_edgar_database` | Opinionated bootstrap: migrate, listed issuers, optional bulk ZIP, references. |
| `load_crm_companies_json` | Load CRM JSON into `CrmCompanyRecord`. |
| `match_crm_sec_titles` | Match CRM names to SEC issuers. |
| `sync_crm_matched_edgar` | Sync submissions/facts for matched CRM rows (rate-limit friendly). |
| `sync_all_companies` | Rate-limited, resumable bulk sync of EDGAR datasets for every company (`--delay`, `--limit`, `--offset`, `--with-ticker-only`, `--leadership-limit`, `--force`, `--user-agent-email`). |
| `sync_derived_metrics` | Compute `DerivedMetric` rows from existing Facts (`--ticker` / `--cik` / `--all`); also the backfill path. |
| `generate_static_site` | Render a static HTML site of company financials (`--ticker`/`--cik`/`--all`, `--output`, `--limit`) with per-company copy/download CSV+JSON. |
| `publish_static_site` | End-to-end public-mirror build: sync a curated ticker set from SEC (submissions, facts, metrics, leadership), then render the static site (`--tickers`, `--output`, `--skip-sync`, `--sync-only`, `--all-warehouse`, `--skip-macro`, `--delay`, `--leadership-limit`, `--force-refresh`, `--base-url`, `--app-url`). `--sync-only` refreshes the serverless dataset without rendering; `--all-warehouse` renders everything already warehoused, offline. Runs in the GitHub Pages + dataset-refresh workflows; see [static-site.md](static-site.md). |
| `sync_leadership` | Extract officers/directors/owners from SEC Forms 3/4/5 (`--ticker`/`--cik`, `--limit`). |
| `compute_stakeholder_assessment` | Compute the transparent people-vs-profits orientation index (`--ticker`/`--cik`/`--all`). |
| `analyze_leadership` | Gated LLM narrative analysis of leadership from SEC filing text (`--ticker`/`--cik`/`--all`, `--no-persist`; needs `ENABLE_AI_ANALYSIS` + `requirements-ai.txt`). |

### `public_data`

| Command | Purpose |
|---------|---------|
| `load_series_bundle` | Register a single bundle JSON via `--file` (e.g. `src/public_data/bundles/core.json`). |
| `sync_series_bundle` | Pull observations for a named bundle, e.g. `--slug core` (FRED needs `FRED_API_KEY`). |
| `refresh_series_bundles` | Register **and** FRED-sync every bundle JSON in the bundles dir — the easiest way to load all macro series (`--dir`, `--no-sync`, `--delay`, `--days-back`). |

Use `python manage.py help <command>` for full arguments.
