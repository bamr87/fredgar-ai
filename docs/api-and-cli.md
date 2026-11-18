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
- **Health probes (UPS-BE-10/11):** three root routes outside `/api/`, all anonymous, unthrottled and sent with `Cache-Control: no-store`. `GET /healthz` is liveness and always answers `200 {"status":"ok"}` without touching a dependency. `GET /readyz` is readiness: it answers `200 {"status":"ok","checks":{"db":"ok","cache":"ok","broker":"ok"}}`, or `503` with `"status":"degraded"` and `error: <ExceptionClass>` under each failed check. `broker` pings the Celery Redis broker and reports `skipped` when tasks run eagerly or the broker is not Redis. `GET /version` answers `{"name","version","commit","built_at"}`: the version comes from `.release-please-manifest.json`, and the commit and build time come from the `GIT_SHA` and `BUILT_AT` build args, or `unknown` when those are not set. `/api/v1/health/` and `/api/v1/health/ready/` remain aliases of the first two. The image `HEALTHCHECK`, the compose `web` healthcheck and the UI's readiness dot all poll `/readyz`, and Vite and nginx proxy all three routes.
- **Throttling:** anonymous and user rates apply everywhere except the health probes (`THROTTLE_ANON`, `THROTTLE_USER`), and the SEC-hitting actions carry the scoped `sec` rate (`THROTTLE_SEC`, default `20/min`).
- **Async jobs:** the sync actions accept `?async=true` and answer `202` with a `task_id`; poll `GET /api/v1/tasks/{task_id}/` for the Celery result (staff only, the same users who can dispatch the job).
- **SEC caching:** reads go DB first and only call SEC when nothing is cached; `?force_refresh=true` refetches on the endpoints whose **Params** column lists it. See [architecture.md](architecture.md).
- **SEC User-Agent:** SEC requires a contact email. The server uses `USER_AGENT_EMAIL`; a request may override it with the `X-Sec-User-Agent-Email` header.
- **Filing text search:** `GET /api/v1/filings/search/?q=…` searches the text of ingested filing documents (ranked full-text search on Postgres, a case-insensitive substring match elsewhere) and returns at most 50 hits. `q` must be at least 2 characters; `form_type` (for example `10-K`) and `cik` narrow the search. `cik` takes a bare, zero-padded or `CIK`-prefixed value (`320193`, `0000320193`, `CIK0000320193`); a value with no digits, or with more than 10 significant digits, is a `400` with a `detail` message rather than a filter that is quietly dropped. Leave `cik` out, or empty, to search every company.

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

## Macro series: FRED transforms and vintages

`GET /api/v1/series-bundles/{slug}/observations/` and `GET /api/v1/public-observations/?series={id}` return the stored FRED observations. Four optional query parameters return them transformed the way the FRED API would (FR-MAC-001, [`transforms.py`](../src/public_data/services/transforms.py)). Without them, both endpoints answer exactly as before.

| Parameter | Values | Default |
| --- | --- | --- |
| `units` | `lin` levels, `chg` change, `ch1` change from a year ago, `pch` percent change, `pc1` percent change from a year ago, `pca` compounded annual rate of change, `cch` continuously compounded rate of change, `cca` continuously compounded annual rate of change, `log` natural log | `lin` |
| `frequency` | `d`, `w` (weekly, ending Friday), `m`, `q`, `sa`, `a` | the series' own |
| `aggregation` | `avg`, `sum`, `eop` (end of period); read only with `frequency` | `avg` |
| `vintage_date` | `YYYY-MM-DD`: the series as FRED published it on that day (ALFRED); needs `ENABLE_FRED_VINTAGES=true` | none: the stored observations |

- **Formulas.** The units follow [FRED's formulas](https://alfred.stlouisfed.org/help#growth_formulas), where `n` is the number of observations per year at the output frequency: daily 260, weekly 52, biweekly 26, monthly 12, quarterly 4, semiannual 2, annual 1. Aggregation runs first, then the units transform.
- **Lags are by period.** x(t-1) is the observation one period earlier at the output frequency: the previous weekday for daily data, or the previous calendar day for a series with weekend observations. When that period is missing, the value is undefined, as FRED's `.` is. Undefined values are left out of the response: the first period of a change, a percentage over zero, and the log of a value that is not positive.
- **Frequency.** Aggregation labels each period as FRED does: the first day of the month, quarter, half-year or year, and the Friday that ends the week. A period still in progress aggregates the observations it has so far. FRED's biweekly target (`bw`) is not offered, because FRED does not document which Wednesdays anchor its two-week periods. Asking one series for a frequency higher than its own is a `400`, as in FRED. A bundle mixes frequencies, so there a series of a lower frequency keeps its own, and each entry in `series` reports its `output_frequency`.
- **Echo.** A transformed response adds `transform`, holding the applied `units`, `frequency`, `aggregation` and `vintage_date`. On `public-observations`, `series` is then required, the rows become `{series, observation_date, value}` newest first (still paginated), and `output_frequency` sits beside the page. An unknown value is a `400` with a `detail`.
- **Vintages.** Off by default. With `ENABLE_FRED_VINTAGES=true`, a `vintage_date` is read from `warehouse.SeriesVintageObservation`, and anyone can read what is stored. When that series and date are not stored yet, a staff user's request fetches them once from FRED, with `realtime_start` and `realtime_end` set to the vintage date, and stores them: like the SEC sync actions, a FRED call that writes rows needs `is_staff`. Anyone else gets a `403` on `public-observations`, and in a bundle that series carries an `error` and no values. `python manage.py sync_series_vintage --series GDPC1 --as-of 2020-01-01` fetches one ahead of time, which a large bundle wants: the first request for a new date makes one FRED call per series. A series FRED cannot supply is a `502` on `public-observations`, and an `error` in a bundle. While the flag is off, `vintage_date` is a `400`.

The Macro page offers the same units, frequency and aggregation. Its Index (=100) option rebases the levels in the browser, since the FRED API has no such unit.
