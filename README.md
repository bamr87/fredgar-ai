# Fredgar AI

> Django + React app for exploring SEC EDGAR company data and FRED macro series, with AI-assisted summaries.

[![CI](https://github.com/bamr87/fredgar-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/bamr87/fredgar-ai/actions/workflows/ci.yml) [![License](https://img.shields.io/github/license/bamr87/fredgar-ai)](LICENSE) [![Live site](https://img.shields.io/badge/live-bamr87.github.io%2Ffredgar--ai-2ea44f)](https://bamr87.github.io/fredgar-ai/)

## Overview

**Fredgar AI** (FRED + EDGAR, with AI) is a Django + Django REST Framework backend with a Vite/React UI for **SEC EDGAR** company data and optional **FRED** macro series, with AI-assisted interpretation and summaries.

## Features

- SEC EDGAR company data through direct SEC APIs (`sec_edgar` app)
- Optional FRED macro series (`public_data` app, needs `FRED_API_KEY`)
- Versioned REST API at `/api/v1/` built with Django REST Framework
- React + TypeScript (Vite) frontend in `frontend/`
- AI-assisted interpretation and summaries of the data

## Stack

- **Backend**: Python 3.12+, Django 5+, DRF, `sec_edgar` (direct SEC APIs), `public_data` (FRED)
- **Frontend**: React + TypeScript (Vite) in [`frontend/`](frontend/)
- **Database**: SQLite by default; set `DATABASE_URL` for PostgreSQL

## Quick start

```bash
git clone https://github.com/bamr87/fredgar-ai.git
cd fredgar-ai
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp src/.env.example src/.env   # set USER_AGENT_EMAIL (required by SEC)
cd src
python manage.py migrate
python manage.py runserver
```

API base: **http://127.0.0.1:8000/api/v1/** (legacy **/api/** mirrors the same routes).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. Optional: set `VITE_API_BASE` (e.g. production API URL). See [`frontend/README.md`](frontend/README.md).

## Environment

See [`src/.env.example`](src/.env.example). Important:

- **`USER_AGENT_EMAIL`**: SEC requires a descriptive `User-Agent` identifying you.
- **`FRED_API_KEY`**: needed for `sync_series_bundle` / FRED observations.
- **`DJANGO_SECRET_KEY`**: set a strong value when `DJANGO_DEBUG=false`.

## Common tasks

Typical flows (from `src/`):

```bash
cd src
python manage.py ingest_htm --url 'https://www.sec.gov/Archives/edgar/data/.../file.htm' --ticker AAPL
python manage.py sync_submissions --ticker AAPL
python manage.py sync_company_facts --ticker AAPL
python manage.py sync_derived_metrics --ticker AAPL
python manage.py generate_static_site --ticker AAPL --output ../site   # static "Wikipedia" site
python manage.py publish_static_site --output ../site   # sync default cohort from SEC + render (the GitHub Pages build)
python manage.py refresh_series_bundles            # register + FRED-sync all series bundles
python manage.py sync_series_bundle --slug core    # or sync one bundle by slug (needs FRED_API_KEY)
```

The static site (`generate_static_site`) renders offline HTML — one page per company with financial statements, derived metrics, filings, and a 23k-row facts table, each with copy-to-clipboard and CSV/JSON downloads. Serve `site/` from any static host (GitHub Pages, S3, nginx). A GitHub Actions workflow ([`.github/workflows/pages.yml`](.github/workflows/pages.yml)) publishes it to **GitHub Pages** on a weekly schedule via `publish_static_site` — the public, no-login mirror of the interactive app. Setup and details: [`docs/static-site.md`](docs/static-site.md).

Same sync actions are available on the API, for example `POST /api/v1/companies/{id}/sync-submissions/` and `POST /api/v1/companies/{id}/sync-facts/`. **Full command list, CRM pipeline, and bulk ZIP loaders** are documented in [`docs/api-and-cli.md`](docs/api-and-cli.md).

Bundles are defined as JSON under [`src/public_data/bundles/`](src/public_data/bundles/). Observations: `GET /api/v1/series-bundles/{slug}/observations/`.

### Sample company list (reference data, not ingested by Django)

[`data/samples/companies-sample.csv`](data/samples/companies-sample.csv) is a small CRM-style export checked into git. Large exports go under **`data/local/`** (gitignored), e.g. `data/local/companies-clean.json` for `load_crm_companies_json`. SEC issuers live in the `warehouse` app after sync/ingest. If an older database still has table `erp_clients_erpclientrow`, drop it or recreate the DB; Django no longer ships that app.

### HTM ingest

The standalone pre-Django scripts have been removed; the Django management commands are the canonical CLI. To ingest one HTM filing:

```bash
cd src
python manage.py ingest_htm --url 'https://www.sec.gov/Archives/.../file.htm' --ticker AAPL
```

## Project structure
- [`src/config/`](src/config/) — Django settings and URLs
- [`src/warehouse/`](src/warehouse/) — `Company`, `Filing`, `Fact`, `DerivedMetric`, peers
- [`src/sec_edgar/`](src/sec_edgar/) — SEC client, HTM parser, ingest + sync services
- [`src/public_data/`](src/public_data/) — external series catalog + FRED sync
- [`src/api/v1/`](src/api/v1/) — versioned REST API
- [`tests/`](tests/) — pytest + pytest-django

Data layout (reference, samples, local): [`data/README.md`](data/README.md).

## Docker Compose

From the repo root, **PostgreSQL + API** (port **8000**), with `./data` mounted for reference JSON and HTM artifacts:

```bash
docker compose up -d --build
curl -s http://127.0.0.1:8000/api/v1/health/
```

Optional env (shell or a `.env` file next to `docker-compose.yml`): `DJANGO_SECRET_KEY`, `USER_AGENT_EMAIL`, `DJANGO_DEBUG`, `CORS_ALLOWED_ORIGINS`. Container entrypoints are summarized in [`docker/README.md`](docker/README.md).

**Vite dev UI** (port **5173**), proxying `/api` to the API container:

```bash
docker compose --profile dev up -d --build
```

For the Compose `frontend` service, `API_PROXY_TARGET=http://web:8000` is set in [`docker-compose.yml`](docker-compose.yml). For Vite on the host, omit it; the default is `http://127.0.0.1:8000` (see [`frontend/.env.example`](frontend/.env.example)).

**Static UI + nginx** (port **8080**), same-origin `/api` proxied to Django:

```bash
docker compose --profile prod up -d --build
```

**CI-style checks in containers** (ruff, `makemigrations --check`, `manage.py check`, pytest against Postgres). Mounts `./data` for reference files used in tests:

```bash
docker compose --profile ci run --rm test
```

Single-image API build (no Compose) still works:

```bash
docker build -t fredgar-ai .
docker run -p 8000:8000 -e USER_AGENT_EMAIL=you@example.com fredgar-ai
```

## Tests & CI

```bash
pytest -q
```

GitHub Actions: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs Ruff, migration checks, `manage.py check`, pytest (SQLite and PostgreSQL), and `npm ci` + production build for the Vite frontend. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for matching local commands.

## Documentation

- **[`docs/README.md`](docs/README.md)** — Index of all technical and reference docs.
- **[`docs/architecture.md`](docs/architecture.md)** — Apps, data flow, DB-first SEC caching.
- **[`docs/api-and-cli.md`](docs/api-and-cli.md)** — REST routes and `manage.py` commands.
- **[`docs/sec-reference/`](docs/sec-reference/)** — SEC API and PDS context (external behavior).
- **[`PRD.md`](PRD.md)** — Product vision and roadmap (see banner there for scope vs code).

## Contributing

Contributions are welcome via pull request. Use [Conventional Commits](https://www.conventionalcommits.org/) and keep the CI checks green. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow. AI agents should start with [CLAUDE.md](CLAUDE.md).

## Changelog

Notable changes are recorded in [CHANGELOG.md](CHANGELOG.md). Tagged versions are on the [releases page](https://github.com/bamr87/fredgar-ai/releases).

## License

Released under the [MIT License](LICENSE).

---

<!-- bamr87-portfolio-footer -->
Part of the [bamr87 portfolio](https://github.com/bamr87) — browse every project on [Amr's GitHub profile](https://github.com/bamr87).
