# Contributing

> How to set up a local environment, run the same lint, test and migration checks as CI, and land a change in fredgar-ai.

Thanks for contributing to **Fredgar AI** (FRED + EDGAR, with AI) — a Django + DRF backend and Vite/React UI for **SEC EDGAR** company data and **FRED** macro series, with AI-assisted analysis. Repo: [`fredgar-ai`](https://github.com/bamr87/fredgar-ai).

## Prerequisites

- Python 3.12+
- Node.js 20+ (for the Vite frontend)
- Optional: Docker with Compose (matches CI-style checks)

## Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp src/.env.example src/.env
# Set USER_AGENT_EMAIL for any command that calls SEC.
# src/.env is loaded automatically by config/settings.py (python-dotenv);
# real environment variables already set take precedence.
```

### Dependencies

Runtime deps are managed with [pip-tools](https://github.com/jazzband/pip-tools): edit [`requirements.in`](requirements.in) (bounded ranges) and regenerate the pinned lock:

```bash
pip-compile requirements.in            # rewrites requirements.txt
pip-compile --upgrade-package django requirements.in   # bump one package
```

Common tasks are wrapped in the [`Makefile`](Makefile): `make lint`, `make test`, `make typecheck`, `make migrations`, `make all`.

Run Django from `src/`:

```bash
cd src
python manage.py migrate
python manage.py runserver
```

`PYTHONPATH` and `DJANGO_SETTINGS_MODULE` are set automatically when using `cd src` and the project layout; tests use `config.settings_test` via [`pyproject.toml`](pyproject.toml) `[tool.pytest.ini_options]`.

## Lint and tests

From the repository root:

```bash
ruff check src tests
ruff format src tests
pytest -q
```

Coverage thresholds apply in Docker CI (`docker compose --profile ci`); local `pytest` runs without the coverage gate unless you pass the same flags as [`docker/ci.sh`](docker/ci.sh).

## Frontend

```bash
cd frontend
npm ci
npm run lint
npm run build
```

## Migrations

After model changes:

```bash
cd src
python manage.py makemigrations
python manage.py makemigrations --check --dry-run   # CI-style
```

## Documentation

- Index: [`docs/README.md`](docs/README.md)
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- API and CLI: [`docs/api-and-cli.md`](docs/api-and-cli.md), with the generated route and command reference in [`docs/reference/`](docs/reference/) (`python3 tools/gen_reference.py --write`)
- Releasing: [`docs/releasing.md`](docs/releasing.md)
- Agent guide: [`AGENTS.md`](AGENTS.md)

## SEC usage

Identify your application with a valid contact in `User-Agent` (`USER_AGENT_EMAIL` / `SEC_USER_AGENT_EMAIL` per settings). Follow [SEC fair access](https://www.sec.gov/os/webmaster-faq#code-support) guidance.
