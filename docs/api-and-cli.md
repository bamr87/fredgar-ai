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
- **Async jobs:** the sync actions accept `?async=true` and answer `202` with a `task_id`; poll `GET /api/v1/tasks/{task_id}/` for the Celery result (staff only, the same users who can dispatch the job).
- **SEC caching:** reads go DB first and only call SEC when nothing is cached; `?force_refresh=true` refetches on the endpoints whose **Params** column lists it. See [architecture.md](architecture.md).
- **SEC User-Agent:** SEC requires a contact email. The server uses `USER_AGENT_EMAIL`; a request may override it with the `X-Sec-User-Agent-Email` header.

The same service functions back the API and the CLI: `POST /api/v1/companies/{id}/sync-submissions/` and `manage.py sync_submissions` both call `sync_submissions_for_company`.

## Company vs macro overlay

`GET /api/v1/companies/{id}/macro-overlay/` lines a company series up with a stored FRED series over the company's own fiscal periods and reports how the two move together (feature FREDGAR-013, requirement FR-ANL-002). The company page's **Macro** tab is its UI: a company-series picker, a series picker fed by the series bundles, a dual-axis chart, a correlation badge and CSV export.

- **Parameters:** exactly one of `metric` (a derived-metric key such as `gross_margin`) or `concept` (an XBRL tag, or a comma-separated priority chain such as `RevenueFromContractWithCustomerExcludingAssessedTax,Revenues`); `series` (the FRED id, matched case-insensitively); `agg=avg|eop` (default `avg`); `annual=1` to keep only full fiscal years; `taxonomy` and `limit` as on `analytics/timeseries/`.
- **Errors:** a missing or unknown parameter is a `400` whose `detail` names it (an unknown `metric` also lists the known ones). A series with no stored observations is a `404`. The endpoint is DB-first and never calls FRED or SEC: store the series first with `refresh_series_bundles` or `sync_series_bundle`.
- **Response:** `rows` of `{period_start, period_end, company_value, series_value, series_observations}`, oldest first; `correlation` `{method: "pearson", r, n}`; `alignment` `{window, aggregation, series_step_days, description, dropped}`, where `dropped` lists each fiscal period that did not align and why; and the `company_series` and `series` metadata.

How periods are aligned ([`macro_overlay.py`](../src/warehouse/services/macro_overlay.py)):

- **Fiscal windows, not calendar windows.** Each company value covers a window. A durational fact covers its own `period_start` to `period_end`. A derived metric takes the window of the longest durational input fact reported for its `period_end`, the fact `compute_derived_metrics` resolves. A point-in-time value (an instant fact such as `Assets`, or a balance-sheet-only metric) covers the span since the previous `period_end` in the series, and the earliest one covers as many days as the window after it.
- **Observations by date.** A series observation belongs to the window its `observation_date` falls in. FRED dates a period by its first day, so a fiscal year from July to June takes the monthly observations dated July 1 through June 1, or the quarterly ones dated July 1 through April 1. A series coarser than the company's periods, such as an annual series against fiscal quarters, aligns only the windows an observation date falls in.
- **Aggregation.** `avg` is the mean of the window's observations; `eop` is the last one.
- **Partly covered windows are dropped, never padded or interpolated.** A window is dropped when an observation dated inside it is missing, wherever it falls. The step is the median spacing of the series' stored observations, and each bound below has three days of slack for weekends, holidays and month lengths. The start bound is a step tighter than the end bound because FRED dates an observation by the first day of its period: a complete series has an observation on the first day of a window that starts on a period boundary, and its last one a period before the end of a window that ends on one.
  - **At the start:** a whole step lies between the window start and its first observation, as when a June fiscal year has no July observation. The reason is `gap` when the observation stored before the window is more than 1.5 steps before that first one, and `series_starts_late` when nothing is stored before the window. When the observation before is a normal step away, nothing is missing: the window starts between two observations.
  - **At the end:** more than a step lies between the window's last observation and its end. The reason is `gap` when the observation stored after the window is more than 1.5 steps after it, and `series_ends_early` when nothing is stored after the window.
  - **Inside:** two consecutive observations in the window are more than 1.5 steps apart, which is a `gap`.
  - Each dropped window is listed in `dropped` with its reason.
- **Correlation.** Pearson r over the aligned pairs; `r` is `null` when fewer than three periods align or one side is constant. It correlates levels, so two trending series, such as revenue and nominal GDP, show a high r without moving together period to period.

## Management commands

Run them from `src/` (being there is what puts `config` and the apps on the path):

```bash
cd src
python manage.py <command> [options]
python manage.py help <command>      # full argument help, with defaults
```

The enrichment pipeline (`enrich_*`) is CLI-only by design: running providers spends SEC and search budget and takes minutes, so it does not belong in a request a browser can retry. The HTTP side only reads its results. See [enrichment.md](enrichment.md).

`publish_static_site` is the GitHub Pages build (sync a curated cohort from SEC, then render); see [static-site.md](static-site.md). The leadership commands and their caveats are in [leadership-methodology.md](leadership-methodology.md).
