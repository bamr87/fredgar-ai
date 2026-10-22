# Fredgar AI

> Django + React app for exploring SEC EDGAR company data and FRED macro series, with AI-assisted summaries.

[![CI](https://github.com/bamr87/fredgar-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/bamr87/fredgar-ai/actions/workflows/ci.yml) [![License](https://img.shields.io/github/license/bamr87/fredgar-ai)](LICENSE) [![Live site](https://img.shields.io/badge/live-bamr87.github.io%2Ffredgar--ai-2ea44f)](https://bamr87.github.io/fredgar-ai/)

## Overview

**Fredgar AI** (FRED + EDGAR, with AI) is a Django + Django REST Framework backend with a Vite/React UI for **SEC EDGAR** company data and optional **FRED** macro series, with AI-assisted interpretation and summaries. A weekly GitHub Pages build publishes a static, no-login mirror of the warehouse at [bamr87.github.io/fredgar-ai](https://bamr87.github.io/fredgar-ai/).

## Features

- SEC EDGAR company data through direct SEC APIs (`sec_edgar` app), cached DB-first to respect SEC fair-access limits
- Optional FRED macro series (`public_data` app, needs `FRED_API_KEY`)
- Versioned REST API at `/api/v1/` built with Django REST Framework, with an OpenAPI schema and Swagger UI
- React + TypeScript (Vite) frontend in `frontend/`
- AI-assisted interpretation and summaries of the data, grounded in SEC filing text
- A static "Wikipedia of company financials" site (`generate_static_site`) and an auditable enrichment pipeline for customer/vendor lists (`enrich_*`)

## Quick start

Clone [bamr87/fredgar-ai](https://github.com/bamr87/fredgar-ai), then from the repo root (Python 3.12+, Node 20+):

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

The legacy `/api/` path mirrors the same routes. Set `VITE_API_BASE` to point the UI at another API; see [`frontend/README.md`](frontend/README.md).

## Stack

- **Backend**: Python 3.12+, Django 6, DRF, `sec_edgar` (direct SEC APIs), `public_data` (FRED), Celery + Redis for async sync jobs
- **Frontend**: React + TypeScript (Vite) in [`frontend/`](frontend/)
- **Database**: SQLite by default; set `DATABASE_URL` for PostgreSQL

## Environment

See [`src/.env.example`](src/.env.example). Important:

- **`USER_AGENT_EMAIL`**: SEC requires a descriptive `User-Agent` identifying you.
- **`FRED_API_KEY`**: needed for `sync_series_bundle` / FRED observations.
- **`DJANGO_SECRET_KEY`**: set a strong value when `DJANGO_DEBUG=false`.

## Common tasks

Typical flows, from `src/`:

```bash
cd src
python manage.py sync_submissions --ticker AAPL
python manage.py sync_company_facts --ticker AAPL
python manage.py sync_derived_metrics --ticker AAPL
python manage.py ingest_htm --url 'https://www.sec.gov/Archives/edgar/data/.../file.htm' --ticker AAPL
python manage.py generate_static_site --ticker AAPL --output ../site   # static "Wikipedia" site
python manage.py publish_static_site --output ../site   # sync the default cohort from SEC + render (the GitHub Pages build)
python manage.py refresh_series_bundles            # register + FRED-sync all series bundles
python manage.py sync_series_bundle --slug core    # or sync one bundle by slug (needs FRED_API_KEY)
```

The same sync actions are on the API, for example `POST /api/v1/companies/{id}/sync-submissions/`. Every route and command is listed in the generated [`docs/reference/`](docs/reference/), and [`docs/api-and-cli.md`](docs/api-and-cli.md) explains how they fit together. The static site renders offline HTML — one page per company with statements, derived metrics, filings and facts, each with copy and CSV/JSON downloads — and [`.github/workflows/pages.yml`](.github/workflows/pages.yml) publishes it weekly; see [`docs/static-site.md`](docs/static-site.md).

Series bundles are JSON under [`src/public_data/bundles/`](src/public_data/bundles/). A small CRM-style sample lives in [`data/samples/companies-sample.csv`](data/samples/companies-sample.csv); large exports go under the gitignored `data/local/` (see [`data/README.md`](data/README.md)).

## Docker Compose

From the repo root, PostgreSQL + the API on port 8000, with `./data` mounted for reference JSON and HTM artifacts:

```bash
docker compose up -d --build
curl -s http://127.0.0.1:8000/api/v1/health/
docker compose --profile dev up -d --build    # + Vite dev UI on :5173, proxying /api to the API container
docker compose --profile prod up -d --build   # + static UI behind nginx on :8080, same-origin /api
docker compose --profile ci run --rm test     # CI-style checks against Postgres
```

Optional env (shell or a `.env` next to `docker-compose.yml`): `DJANGO_SECRET_KEY`, `USER_AGENT_EMAIL`, `DJANGO_DEBUG`, `CORS_ALLOWED_ORIGINS`. The container scripts are described in [`docker/README.md`](docker/README.md). A single-image build without Compose also works: `docker build -t fredgar-ai .` then `docker run -p 8000:8000 -e USER_AGENT_EMAIL=you@example.com fredgar-ai`.

## Documentation

- **[`docs/README.md`](docs/README.md)** — the index of every document in the repo.
- **[`docs/architecture.md`](docs/architecture.md)** — apps, data flow, DB-first SEC caching.
- **[`docs/api-and-cli.md`](docs/api-and-cli.md)** — how the REST API and `manage.py` commands fit together, with the generated [route](docs/reference/api-routes.md) and [command](docs/reference/management-commands.md) reference.
- **[`PRD.md`](PRD.md)** — product vision and roadmap (its scope table separates shipped from planned).

## Project structure

- [`src/config/`](src/config/) — Django settings and URLs
- [`src/warehouse/`](src/warehouse/) — every model: `Company`, `Filing`, `Fact`, `DerivedMetric`, peers, CRM staging, enrichment
- [`src/sec_edgar/`](src/sec_edgar/) — SEC client, HTM parser, ingest + sync services
- [`src/public_data/`](src/public_data/) — external series catalog + FRED sync
- [`src/enrichment/`](src/enrichment/) — the claim-based enrichment framework
- [`src/api/v1/`](src/api/v1/) — versioned REST API
- [`frontend/`](frontend/) — the Vite/React UI
- [`tests/`](tests/) — pytest + pytest-django
- [`docs/`](docs/) — topic docs, ADRs and the generated reference

## Development

Build, test and lint commands are in [Quick start](#quick-start); `make all` runs the blocking CI checks (lint, migrations, tests with the coverage gate). [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs Ruff, migration checks, `manage.py check`, pytest (SQLite and PostgreSQL) and the frontend build. After changing a route, a view docstring or a command, regenerate the reference with `python3 tools/gen_reference.py --write`. Agents and contributors: start with [`AGENTS.md`](AGENTS.md).

## Contributing

Contributions are welcome via pull request. Use [Conventional Commits](https://www.conventionalcommits.org/) and keep the CI checks green. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow; AI agents start with [AGENTS.md](AGENTS.md).

## Changelog

Notable changes are recorded in [CHANGELOG.md](CHANGELOG.md), written by release-please ([docs/releasing.md](docs/releasing.md)). Tagged versions are on the [releases page](https://github.com/bamr87/fredgar-ai/releases).

## License

Released under the [MIT License](LICENSE).

---

<!-- bamr87-portfolio-footer -->
Part of the [bamr87 portfolio](https://github.com/bamr87) — browse every project on [Amr's GitHub profile](https://github.com/bamr87).
