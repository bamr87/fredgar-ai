<!-- kit: sdlc v0.1.0 · AGENTS.md is the CANONICAL agent instructions file (decision D4, UPS-AGENT-07/08). -->

# fredgar-ai

> Django + DRF backend and Vite/React UI for SEC EDGAR company data and FRED macro series, with AI-assisted analysis layered on top.

## What this repo is

**Fredgar AI** (FRED + EDGAR, with AI) serves SEC EDGAR company data (filings, XBRL facts, derived metrics, leadership) and optional FRED macro series through a versioned REST API, a Vite/React UI in [`frontend/`](frontend/), and a static public mirror on GitHub Pages. Python lives under [`src/`](src/), tests under [`tests/`](tests/). The database is SQLite by default and PostgreSQL when `DATABASE_URL` is set (Docker/CI Postgres uses user/password/db `fredgar`; the CI test database is `test_fredgar`). A change is done when `ruff check src tests`, `pytest -q` and the migration check pass, a frontend change also passes `npm run lint && npm run build`, the generated reference is current, and the nearest README or `docs/` page reflects it.

## Stack & commands

Python 3.12+, Django 6 + DRF, Celery + Redis, React + TypeScript (Vite). `manage.py` runs from **`src/`** (that is what puts `config` and the apps on the path); lint and tests run from the repo root.

```bash
# install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp src/.env.example src/.env        # set USER_AGENT_EMAIL (SEC requires it)

# run the API on http://127.0.0.1:8000/api/v1/
(cd src && python manage.py migrate && python manage.py runserver)

# run the UI on http://127.0.0.1:5173 (proxies /api to :8000)
(cd frontend && npm ci && npm run dev)

# test and lint (from the repo root)
pytest -q
ruff check src tests
(cd src && python manage.py makemigrations --check --dry-run)
(cd frontend && npm run lint && npm run build)
```

More, as needed:

```bash
pytest tests/api/test_filings_api.py::test_name     # one test (or -k keyword)
ruff format src tests                               # format
make test                                           # pytest with the CI coverage gate (--cov-fail-under=50)
python3 tools/gen_reference.py --write              # regenerate docs/reference/ (--check to verify)
python3 tools/docs_index.py --write                 # regenerate the docs/README.md index
python3 tools/unwrap-prose.py --check               # markdown: one paragraph per line (--write to fix)

# enrichment chain (from src/; see docs/enrichment.md)
python manage.py enrich_init --dataset X --csv ../data/list.csv --mapping manufacturing_v1
python manage.py enrich_plan --dataset X            # what WOULD run, before spending anything
python manage.py enrich_run --dataset X --no-web    # free + DB-first providers; resumable
python manage.py enrich_resolve --dataset X         # claims -> golden record
python manage.py enrich_link --dataset X            # verified CIK -> warehouse Company
python manage.py enrich_export --dataset X --out ../data/enrichment/master.csv

# Docker (from the repo root)
docker compose up -d --build                        # Postgres + API on :8000
docker compose --profile dev up -d --build          # + Vite dev UI on :5173
docker compose --profile prod up -d --build         # + nginx static UI on :8080
docker compose --profile ci run --rm test           # the CI suite against Postgres
```

Every route and command is listed in the generated [`docs/reference/`](docs/reference/) ([api-routes.md](docs/reference/api-routes.md), [management-commands.md](docs/reference/management-commands.md)); [`docs/api-and-cli.md`](docs/api-and-cli.md) explains how they fit together.

**Test settings:** [`pyproject.toml`](pyproject.toml) `[tool.pytest.ini_options]` is the only pytest config — `DJANGO_SETTINGS_MODULE = config.settings_test`, `pythonpath = ["src"]`, the `slow`/`integration`/`requires_network` markers — so local, CI and Docker runs match. [`settings_test`](src/config/settings_test.py) imports `settings.py`, turns on `DEBUG` and the fast MD5 hasher, restricts `ALLOWED_HOSTS` and neutralizes DRF throttles. The coverage gate runs in CI/Docker (`docker/ci.sh`) and `make test`, not in a bare `pytest`.

## Layout

| Path | What lives there |
| --- | --- |
| `src/` | The Django project: apps `warehouse`, `sec_edgar`, `public_data`, `enrichment`, `api`, and `config` (below) |
| `tests/` | pytest + pytest-django suite, one folder per app |
| `frontend/` | React + TypeScript (Vite) UI — see [`frontend/README.md`](frontend/README.md) |
| `data/` | Committed reference JSON, samples, enrichment lists; `data/local/` is gitignored — see [`data/README.md`](data/README.md) |
| `docs/` | Topic docs, ADRs (`docs/adr/`), the generated `docs/reference/`; index at [`docs/README.md`](docs/README.md) |
| `docker/` | Container entrypoint and CI scripts — see [`docker/README.md`](docker/README.md) |
| `tools/` | Repo scripts (reference generator, docs index, prose gate) — see [`tools/README.md`](tools/README.md) |
| `features/`, `verify/` | The feature index and the user-scenario verification kit |
| `notebooks/` | Exploratory notebooks over the same pipeline |

## Conventions

- **Backlog of record:** GitHub Issues with the fleet labels (`.github/sdlc.yml` `backlog.mode: issues`). Pick up issues labelled `agent:ready`; never touch `agent:hold` or `human-review`.
- **Definition of Done:** the fleet default pull request template (inherited; this repo has none). Every box is ticked before merge.
- **Decisions:** ADRs in `docs/adr/NNNN-slug.md`, indexed in [`docs/adr/README.md`](docs/adr/README.md). Add one for anything hard to reverse.
- **Commits:** Conventional Commits (`feat fix docs style refactor test chore perf ci build`). The PR title is the squash subject.
- **Branches:** `feature/`, `fix/`, `docs/`, `refactor/`, `test/` or `chore/` off `main`.
- **Changelog:** `CHANGELOG.md` is written by release-please from the PR titles ([`docs/releasing.md`](docs/releasing.md)). Never edit it, or a version number, by hand.
- **Never:** push to `main` directly, commit secrets, suppress type errors, leave empty exception handlers, or edit generated files by hand (`docs/reference/*.md`, the `docs/README.md` index span).
- **Models:** new persisted state goes in `warehouse` (no other app defines models); run `makemigrations` — CI fails on a missing migration.
- **Tests never hit the network:** mock SEC/FRED with `responses`. CI does not deselect the `requires_network` marker, so never rely on it to keep a live call out of CI.
- **Generated reference:** after changing a route, a view or command docstring, or a command's options, run `python3 tools/gen_reference.py --write`; `tests/test_docs_reference.py` fails while it is stale.
- **Markdown:** one paragraph per line (`python3 tools/unwrap-prose.py --check`; CI enforces it).

## Architecture

### Apps (under `src/`)

- **`warehouse`** — every persisted model ([`models.py`](src/warehouse/models.py)): `Company`, `ListedIssuer`, `Filing`, `Section`, `Table`, `FilingDocument`, `Fact`, `DerivedMetric`, `PeerGroup`, CRM staging (`CrmCompanyRecord`), the SEC JSON cache (`EdgarSecPayload`, `EdgarEntitySyncState`), the Company-360 layer (`DataSource`, `ExternalIdentifier`, `ContentChunk`) and the `Enrichment*` models. Also the Celery tasks ([`tasks.py`](src/warehouse/tasks.py)).
- **`sec_edgar`** — SEC HTTP client, HTM/SGML parsing, ingest and sync services. No models.
- **`public_data`** — external time-series registry (`ExternalSeries`, `SeriesBundle`, `SeriesObservation`) and FRED sync; bundles are JSON under `src/public_data/bundles/`.
- **`enrichment`** — the claim-based enrichment framework. No models of its own.
- **`api`** — DRF views only; routes in [`api/v1/urls.py`](src/api/v1/urls.py).
- **`config`** — settings, URLs, Celery, WSGI/ASGI. Settings fail fast on insecure production config.

### Rules that hold the system together

- **Thin views and commands, fat services.** Logic lives in `*/services/`; the DRF viewsets and the `manage.py` commands call the **same** functions (`POST /companies/{id}/sync-submissions/` and `manage.py sync_submissions` both call `sync_submissions_for_company`). Change the service, not the two callers.
- **DB-first SEC reads.** Raw SEC JSON is cached in `EdgarSecPayload` keyed by `(cik, kind)`; reads go DB → SEC → save through [`edgar_sec_payload.py`](src/sec_edgar/services/edgar_sec_payload.py) and return the cached row unless `force_refresh=True` (`?force_refresh=true` on the API, `--force-refresh`-style flags on commands). SEC enforces fair-access limits, so never add a live call where a payload exists. `ListedIssuer` caches `company_tickers.json` so ticker/name search never hits SEC.
- **SEC client and User-Agent.** [`SecEdgarClient`](src/sec_edgar/client.py) does all HTTP to `data.sec.gov`/`www.sec.gov` with `tenacity` retries and `429` → `RuntimeError`. SEC requires a contact email: `USER_AGENT_EMAIL`, overridable per request with the `X-Sec-User-Agent-Email` header ([`sec_user_agent.py`](src/api/sec_user_agent.py)). `sec_edgar/adapters/` defines the `EdgarDataSource` protocol; `DirectEdgarAdapter` is the real implementation.
- **API versioning.** `/api/v1/` is canonical; `/api/` is a legacy alias of the same URLconf. Add routes in `api/v1/` only. OpenAPI at `/api/v1/schema/`, Swagger UI at `/api/v1/docs/`.
- **Auth.** Token + session; reads are public, writes and sync actions need `is_staff` (`IsAdminOrReadOnly`).
- **Async jobs.** Sync actions accept `?async=true` → `202` + `task_id`; poll `GET /api/v1/tasks/{id}/`. Tests run Celery eagerly (`CELERY_TASK_ALWAYS_EAGER`).
- **Computation tier.** `compute_derived_metrics` / `build_financial_statement` ([`warehouse/services/edgar/`](src/warehouse/services/edgar/)) turn `Fact` rows plus `data/reference/financial_model.json` into `DerivedMetric` rows and statements. KPI formulas run through a safe AST walker, never `eval`; metric computation runs **outside** the facts atomic block.
- **Filing corpus.** `ingest_submission` splits a full submission `.txt` into `FilingDocument` rows (SGML parser ported from OpenEDGAR, MIT); raw bytes go to content-addressed storage ([`storage.py`](src/sec_edgar/storage.py), LOCAL/S3 by SHA-1); text is searchable at `/filings/search/` (Postgres FTS, SQLite `icontains` fallback).
- **Company-360.** `GET /companies/{id}/profile/` consolidates identity, financials, filings, documents and CRM with provenance; `ContentChunk` + a pluggable `Embedder` (off by default) are the retrieval foundation.
- **Leadership and stakeholder analytics** ([`docs/leadership-methodology.md`](docs/leadership-methodology.md)). `sync_leadership` reads SEC Forms 3/4/5 into `Person`/`LeadershipPosition`; `compute_stakeholder_assessment` is a transparent, source-cited capital-allocation heuristic, **not** a personal rating. LinkedIn and transcripts are never scraped. The LLM analyzer ([`leadership_ai.py`](src/warehouse/services/leadership_ai.py)) works **only from ingested SEC filing excerpts**, forbids invented quotes and character judgments, schema-validates its output, and degrades to `NoopAnalyzer` (no API call) unless the optional `anthropic` SDK (`requirements-ai.txt`) **and** a credential exist. It is on by default (`ENABLE_AI_ANALYSIS`, `AI_ANALYSIS_MODEL=claude-opus-5-5`) and authenticates token-first with `CLAUDE_CODE_OAUTH_TOKEN` (Bearer + `oauth-2025-04-20` beta header), `ANTHROPIC_API_KEY` as fallback — set only one.
- **Static site** ([`docs/static-site.md`](docs/static-site.md)). `generate_static_site` renders an offline HTML mirror from the same profile/statements/analytics services; `publish_static_site` (sync a cohort, then render) is what [`pages.yml`](.github/workflows/pages.yml) runs. GitHub Pages is offline (`--skip-sync`); only the local/cloud app has the API and AI.
- **Enrichment** ([`docs/enrichment.md`](docs/enrichment.md)). A provider **never writes to a record** — it emits `Claim`s with value, confidence and evidence, and [`core/golden.py`](src/enrichment/core/golden.py) resolves them once, *precedence over confidence*; close disagreement becomes the `contested` queue. Runs are resumable, isolated per provider, and budgeted (`--max-fetch/--max-search/--max-api`). Nothing derived from an EDGAR CIK may outrank that CIK; estimates (`revenue_model`) are never blended with reported figures.
- **Data directory.** `data/reference/` is read at runtime **and in tests** (and copied into images) — don't break it. Filing HTM downloads go to `EDGAR_DATA_DIR` (default: repo `data/`). The proposed content-addressed extract store is a spec only: [`docs/distributed-storage.md`](docs/distributed-storage.md).

[`PRD.md`](PRD.md) is partly aspirational — check its scope table for what is implemented.

## Fleet context

Member of the bamr87 fleet. The standards live in the hub: <https://github.com/bamr87/bamr87/tree/main/specs> (the Universal Project Standard). The repo's SDLC declaration is [`.github/sdlc.yml`](.github/sdlc.yml); `ci.yml` runs this repo's own jobs beside the hub's shared `standard-ci.yml` gate, and `conformance.yml` / `verify.yml` call the fleet conformance and verification workflows. This repo is a submodule of the hub: commit and push here first; the hub bumps its pointer afterwards.

## Standard deviations

none
