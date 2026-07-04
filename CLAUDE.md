# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Fredgar AI** (FRED + EDGAR, with AI) — a Django + DRF backend serving **SEC EDGAR** company data (filings, XBRL facts) and optional **FRED** macro series, with a Vite/React frontend in [`frontend/`](frontend/) and AI-assisted analysis layered on top. Python lives under [`src/`](src/); tests under [`tests/`](tests/). Database is SQLite by default, PostgreSQL when `DATABASE_URL` is set (Docker/CI Postgres defaults to user/password/db `fredgar`; the CI ephemeral test database is `test_fredgar`).

## Commands

All `manage.py` commands run from **`src/`** — being in that directory plus `manage.py` is what puts `config` settings and the apps on the path. Lint/test run from the repo root.

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp src/.env.example src/.env        # set USER_AGENT_EMAIL (SEC requires it)

# Backend
cd src && python manage.py migrate && python manage.py runserver   # http://127.0.0.1:8000/api/v1/

# Tests (from repo root)
pytest -q
pytest tests/api/test_filings_api.py                 # one file
pytest tests/api/test_filings_api.py::test_name      # one test
pytest -k edgar_db_first                             # by keyword

# Lint / format (must pass for CI; ruff line-length 100, rules E,F,I,W)
ruff check src tests
ruff format src tests

# Migrations after model changes
cd src && python manage.py makemigrations
cd src && python manage.py makemigrations --check --dry-run   # CI gate; CI fails on missing migrations

# Frontend (from frontend/)
npm ci && npm run dev      # Vite :5173, proxies /api -> :8000
npm run lint && npm run build

# Docker (from repo root)
docker compose up -d --build                    # Postgres + API on :8000
docker compose --profile dev up -d --build      # + Vite dev UI on :5173
docker compose --profile prod up -d --build     # + nginx static UI on :8080
docker compose --profile ci run --rm test       # full CI suite vs Postgres (ruff, migration check, pytest w/ coverage gate)
```

### Test settings

[`pyproject.toml`](pyproject.toml) `[tool.pytest.ini_options]` is the single pytest config: it sets `DJANGO_SETTINGS_MODULE = config.settings_test`, `pythonpath = ["src"]`, `testpaths`, and the markers (`slow`, `integration`, `requires_network`). A bare local `pytest`, CI, and Docker all run against `config.settings_test`. *(There used to be a `pytest.ini` that overrode this with `config.settings`; it was removed so local == CI.)*

[`config/settings_test`](src/config/settings_test.py) imports `settings.py` and flips on `DEBUG` + the fast MD5 password hasher, restricts `ALLOWED_HOSTS`, and neutralizes DRF throttles so tests never hit 429s. The coverage gate (`--cov-fail-under`, currently 50) is applied in CI/Docker (`docker/ci.sh`, `ci.yml`) and via `make test`, not a bare `pytest`.

## Architecture

### Apps (under `src/`)
- **`warehouse`** — all persisted models ([`warehouse/models.py`](src/warehouse/models.py)): `Company`, `ListedIssuer`, `Filing`, `Section`, `Table`, `FilingDocument`, `Fact`, `DerivedMetric`, `PeerGroup`, CRM staging (`CrmCompanyRecord`), the SEC JSON cache (`EdgarSecPayload`, `EdgarEntitySyncState`), and the Company-360 layer (`DataSource`, `ExternalIdentifier`, `ContentChunk`). No other app defines models. Also holds the Celery tasks ([`warehouse/tasks.py`](src/warehouse/tasks.py)).
- **`sec_edgar`** — SEC HTTP client, HTM parsing, and the ingest/sync services. No Django models of its own.
- **`public_data`** — external time-series registry (`ExternalSeries`, `SeriesBundle`, `SeriesObservation`) and FRED sync.
- **`api`** — DRF views only; the route table lives in [`api/v1/urls.py`](src/api/v1/urls.py).
- **`config`** — settings, URLs, WSGI/ASGI.

### Services hold the logic (thin views/commands, fat services)
Business logic lives in `*/services/` modules. Both the DRF viewsets ([`api/v1/views.py`](src/api/v1/views.py)) and the `manage.py` commands (`*/management/commands/`) are thin wrappers that call the **same** service functions — e.g. `POST /companies/{id}/sync-submissions/` and `manage.py sync_submissions` both call `sync_submissions_for_company`. When changing ingest/sync behavior, edit the service, not the two callers.

### Key subsystems
- **Computation tier** — `compute_derived_metrics` / `build_financial_statement` ([`warehouse/services/edgar/`](src/warehouse/services/edgar/)) turn `Fact` rows + `data/reference/financial_model.json` (concept_groups, derived_kpis, statement_schemas) into `DerivedMetric` rows and statement views. KPI formulas are evaluated with a safe AST walker, never `eval`. Metric computation runs **outside** the facts atomic block.
- **Async jobs** — Celery + Redis ([`config/celery.py`](src/config/celery.py), [`warehouse/tasks.py`](src/warehouse/tasks.py)). Sync actions accept `?async=true` → 202 + `task_id`; poll `GET /api/v1/tasks/{id}/`. Tests run eager (`CELERY_TASK_ALWAYS_EAGER`).
- **Filing corpus** — `ingest_submission` decomposes a full SEC submission `.txt` into `FilingDocument` rows (SGML parser ported from OpenEDGAR, MIT). Raw bytes go to content-addressed storage ([`sec_edgar/storage.py`](src/sec_edgar/storage.py), LOCAL/S3 by SHA-1); text is extracted (BeautifulSoup; Tika when `ENABLE_TIKA`) and full-text searchable at `/filings/search/` (Postgres FTS, SQLite `icontains` fallback).
- **Company-360** — `GET /companies/{id}/profile/` consolidates identity + financials + filings + documents + CRM with provenance; `/companies/compare/` does cohort analytics. `ContentChunk` + a pluggable `Embedder` (off by default; pgvector is the prod upgrade) are the AI-retrieval foundation.
- **Leadership & stakeholder analytics** — `sync_leadership` extracts officers/directors/owners from SEC Forms 3/4/5 ([`sec_edgar/parsers/ownership.py`](src/sec_edgar/parsers/ownership.py), [`warehouse/services/leadership.py`](src/warehouse/services/leadership.py)) into `Person`/`LeadershipPosition`. `compute_stakeholder_assessment` ([`warehouse/services/stakeholder.py`](src/warehouse/services/stakeholder.py)) produces a **transparent, source-cited people-vs-profits index** (reinvestment vs payout, capex/local proxy, R&D, insider alignment) — a heuristic about capital allocation, **not** a personal rating; every input is disclosed with caveats. See [`docs/leadership-methodology.md`](docs/leadership-methodology.md). LinkedIn/transcripts are **not scraped** (pluggable licensed/manual only). The optional **LLM narrative analyzer** ([`warehouse/services/leadership_ai.py`](src/warehouse/services/leadership_ai.py), `analyze_leadership` cmd / `POST /companies/{id}/analyze-leadership/`) extracts initiatives/verbatim-quotes/direction **strictly from ingested SEC filing excerpts** into `LeadershipAnalysis` — **enabled by default with Claude** as the provider (`ENABLE_AI_ANALYSIS` default on; `AI_ANALYSIS_MODEL=claude-opus-4-8`), authenticated **token-first** via a Claude Code OAuth token (`CLAUDE_CODE_OAUTH_TOKEN`, sent as a Bearer `auth_token` + `oauth-2025-04-20` beta header) with `ANTHROPIC_API_KEY` as fallback (set only one — both 401). It degrades to the `NoopAnalyzer` (no API call) unless the lazy-optional `anthropic` SDK (`requirements-ai.txt`) **and** a credential are both present. The system prompt forbids invented quotes and personal/character judgments; results are schema-validated and degrade gracefully (no fabrication on error).
- **Static site** — `manage.py generate_static_site` ([`warehouse/services/static_site.py`](src/warehouse/services/static_site.py), templates in `warehouse/templates/staticsite/`) renders a fully static, offline "Wikipedia of company financials": one HTML page per company (infobox, statements, metrics, filings, documents, facts) + a landing/hero `index.html` (headline, a live JS "search a real company" demo built from data already computed per company — no extra queries, no client fetches, works without JS too — feature tour, editions comparison) with the full searchable company index preserved below it, plus per-company copy-to-clipboard and CSV/JSON downloads, and an optional **FRED macro section** (`macro/` — bundle pages with server-rendered SVG sparklines + `observations.csv`/`bundle.json`, built by [`public_data/services/static_export.py`](src/public_data/services/static_export.py); synced at publish time only when `FRED_API_KEY` is set, omitted when no series data exists). Build-time; reuses the profile/statements/analytics services. `manage.py publish_static_site` ([`static_site_publish.py`](src/warehouse/services/static_site_publish.py)) is the end-to-end publish pipeline (sync a curated ticker cohort from SEC → render) used by the **GitHub Pages** workflow ([`.github/workflows/pages.yml`](.github/workflows/pages.yml)) to publish the public no-login mirror; cross-links between the mirror and the interactive app come from `STATIC_SITE_*` settings / `VITE_STATIC_SITE_URL`. See [`docs/static-site.md`](docs/static-site.md).
- **Auth** — token + session; reads public, writes/sync require `is_staff` (`IsAdminOrReadOnly`). Settings fail-fast on insecure prod config.

### DB-first SEC reads (the core caching pattern)
Raw SEC JSON is cached in the `EdgarSecPayload` table keyed by `(cik, kind)`. Read paths go **DB → SEC API → save**: see [`edgar_sec_payload.py`](src/sec_edgar/services/edgar_sec_payload.py) (`get_submissions_payload`, `get_company_facts_payload`). They return the cached row unless `force_refresh=True`. This is deliberate — SEC enforces fair-access rate limits, so avoid live calls when a payload exists. To bypass the cache, thread `force_refresh` through (services), or pass `?force_refresh=true` (API) / `--force-refresh`-style flags (commands). `ListedIssuer` similarly caches `company_tickers.json` so ticker/name search never hits SEC.

### EDGAR data source adapter
`sec_edgar/adapters/` defines an `EdgarDataSource` Protocol ([`base.py`](src/sec_edgar/adapters/base.py)). `DirectEdgarAdapter` ([`direct.py`](src/sec_edgar/adapters/direct.py)) is the real implementation wrapping `SecEdgarClient`.

### SEC client and User-Agent
[`sec_edgar/client.py`](src/sec_edgar/client.py) (`SecEdgarClient`) does all HTTP to `data.sec.gov` / `www.sec.gov`, with `tenacity` retries and explicit `429` → `RuntimeError`. SEC **requires** a contact email in `User-Agent`; it resolves from the `USER_AGENT_EMAIL` env var, and API requests may override it per-call via the `X-Sec-User-Agent-Email` header ([`api/sec_user_agent.py`](src/api/sec_user_agent.py)).

### API versioning
`/api/v1/` is canonical; `/api/` is a legacy alias that includes the exact same urlconf ([`api/urls.py`](src/api/urls.py)). Add routes in `api/v1/` only. OpenAPI 3 schema at `/api/v1/schema/` + Swagger UI at `/api/v1/docs/` (drf-spectacular); [`docs/api-and-cli.md`](docs/api-and-cli.md) is the human-readable route inventory.

### Data directory ([`data/`](data/README.md))
- `data/reference/` — committed JSON consumed by `sec_edgar.reference_data` at **runtime and in tests** (also copied into Docker images); don't break it.
- `data/samples/` — small committed example exports.
- `data/local/` — gitignored drop zone for large CRM/ERP exports (e.g. `companies-clean.json` for `load_crm_companies_json`).
- Filing HTM downloads go to `EDGAR_DATA_DIR` (defaults to repo `data/`).

## Conventions
- New persisted state → add the model to `warehouse` and run `makemigrations` (CI fails on missing migrations).
- Tests use `pytest` + `pytest-django` + `responses` (mock SEC/FRED — tests must not hit the live network; the `requires_network` marker is excluded from CI).
- Reference docs: [`docs/architecture.md`](docs/architecture.md), [`docs/api-and-cli.md`](docs/api-and-cli.md) (full command + route list), [`docs/sec-reference/`](docs/sec-reference/). [`PRD.md`](PRD.md) is aspirational — check its banner for what's actually implemented.
