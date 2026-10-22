# API and CLI

> How the REST API and the `manage.py` commands fit together — base paths, auth, async jobs and caching flags — with links to the generated route and command reference.

The route and command tables themselves are generated from the source, so they cannot drift from it:

- **[reference/api-routes.md](reference/api-routes.md)** — every route: method, path, view, access rule, the parameters the handler reads, and its summary.
- **[reference/management-commands.md](reference/management-commands.md)** — every management command, grouped by app, with its help text and options.

Regenerate both with `python3 tools/gen_reference.py --write` after changing a route, a view docstring or a command; `tests/test_docs_reference.py` fails while they are stale. The summaries come from the view and command docstrings and `help` strings, so improve those rather than the generated files.

## REST API

- **Base path:** `/api/v1/` is canonical. `/api/` is a legacy alias that includes the same URLconf ([`src/api/urls.py`](../src/api/urls.py)); add routes in `src/api/v1/` only.
- **Auth:** token and session authentication. Reads are public; writes and every SEC-hitting action need a staff user (`api.permissions.IsAdminOrReadOnly`, the DRF default in `src/config/settings.py`).
- **OpenAPI:** `drf-spectacular` serves the OpenAPI 3 schema at `/api/v1/schema/` and Swagger UI at `/api/v1/docs/`. Responses are JSON; the browsable API renderer is added only when `DJANGO_DEBUG` is on.
- **Throttling:** anonymous and user rates apply everywhere (`THROTTLE_ANON`, `THROTTLE_USER`), and the SEC-hitting actions carry the scoped `sec` rate (`THROTTLE_SEC`, default `20/min`).
- **Async jobs:** the sync actions accept `?async=true` and answer `202` with a `task_id`; poll `GET /api/v1/tasks/{task_id}/` for the Celery result.
- **SEC caching:** reads go DB first and only call SEC when nothing is cached; `?force_refresh=true` refetches on the endpoints whose **Params** column lists it. See [architecture.md](architecture.md).
- **SEC User-Agent:** SEC requires a contact email. The server uses `USER_AGENT_EMAIL`; a request may override it with the `X-Sec-User-Agent-Email` header.

The same service functions back the API and the CLI: `POST /api/v1/companies/{id}/sync-submissions/` and `manage.py sync_submissions` both call `sync_submissions_for_company`.

## Management commands

Run them from `src/` (being there is what puts `config` and the apps on the path):

```bash
cd src
python manage.py <command> [options]
python manage.py help <command>      # full argument help, with defaults
```

The enrichment pipeline (`enrich_*`) is CLI-only by design: running providers spends SEC and search budget and takes minutes, so it does not belong in a request a browser can retry. The HTTP side only reads its results. See [enrichment.md](enrichment.md).

`publish_static_site` is the GitHub Pages build (sync a curated cohort from SEC, then render); see [static-site.md](static-site.md). The leadership commands and their caveats are in [leadership-methodology.md](leadership-methodology.md).
