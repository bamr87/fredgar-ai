# Static site — the public mirror on GitHub Pages

Fredgar AI ships two front ends over the same warehouse:

| | Interactive app ([`frontend/`](../frontend/)) | Static mirror (this doc) |
|---|---|---|
| **Audience** | Account-based users (token/session auth; reads public, writes/sync staff-only) | Anyone — no account, no backend |
| **Stack** | Vite/React SPA → Django/DRF API | Plain HTML/CSS/JS generated at build time |
| **Freshness** | Live (on-demand SEC/FRED syncs) | Rebuilt on a schedule (weekly + manual) |
| **Hosting** | Docker / nginx (see `docker-compose.yml`) | **GitHub Pages** |

Both are rendered from the same services (`build_company_context` reuses the
profile/statements/analytics code), so the mirror shows exactly what the API does.

## What gets published

One page per company (infobox, headline snapshot, financial statements with per-line SEC
source links, derived metrics, leadership, stakeholder index, filings, documents, XBRL fact
preview) plus:

- `index.html` — the landing/hero page: headline, a live client-side "search a real company"
  demo widget (built from data already computed per company during the publish loop — no
  extra queries, no client fetches), a feature tour of what's mirrored here vs. app-only, an
  editions comparison, a disclosure section, and the full searchable company table (`#browse`,
  unchanged behavior from before) below the marketing content
- `about.html` — data sources, methodology, and the two-front-ends story
- `macro/` — the **FRED macro section** (when series data is warehoused): `macro/index.html`
  lists the curated theme bundles; `macro/<slug>/index.html` renders each bundle's series with
  latest value, 1M/1Y deltas, a server-rendered SVG sparkline (no JS required), curation notes,
  industry-relevance tags, and a link back to the series on fred.stlouisfed.org — plus
  per-bundle `observations.csv` (full synced history, long format) and `bundle.json`.
  Includes the required FRED® API attribution. Omitted entirely when nothing is synced —
  no empty shell pages, and the "Macro" nav link only appears when the section exists.
- per-company `company.json`, `facts.csv`, `metrics.csv`, `statements.csv`, `filings.csv`,
  `leadership.csv`; site-wide `companies.json` / `companies.csv`
- `.nojekyll` (always) and `sitemap.xml` / `robots.txt` (when a base URL is configured)

### The landing page's live demo

`generate_site()` collects a small "featured companies" list while it's already looping over
every company to render their pages — zero additional DB queries. Featured companies are
preferred by whether they have any of the three demo-shown concepts (Revenue, Net Income,
Total Assets) and then by richest data (`counts.facts`), capped at `FEATURED_LIMIT` (8). Their
identity, headline figures, and fact/filing counts are rendered as ordinary server-side HTML
(`.example-card` elements) — visible and fully readable with JavaScript disabled. A small
vanilla-JS enhancement (`{% block script %}` in `index.html`) adds a `.js` class to `<html>`,
which is what actually collapses the cards to one-at-a-time with pill-switching and enables the
search-filter box; without JS, every example simply renders stacked. Company data with no
matching headline concept still appears in the demo with a graceful fallback message instead of
blank figures.

## The pipeline

[`publish_static_site`](../src/warehouse/management/commands/publish_static_site.py) →
[`warehouse/services/static_site_publish.py`](../src/warehouse/services/static_site_publish.py):

1. For each ticker: resolve/create the `Company`, sync submissions + XBRL facts from SEC
   EDGAR (DB-first payload cache, paced with `--delay`), compute derived metrics, and
   best-effort sync leadership (Forms 3/4/5). A failing ticker is reported and skipped —
   never aborts the publish.
2. If a `FRED_API_KEY` is present (and `--skip-macro` isn't passed), refresh the FRED series
   bundles (`refresh_series_bundles`) so the macro section publishes with fresh data. No key →
   the sync is skipped and the macro section renders only from already-warehoused data (or is
   omitted). A failing FRED sync never blocks the company publish.
3. Render the site with `generate_site`
   ([`warehouse/services/static_site.py`](../src/warehouse/services/static_site.py)); macro
   context comes from
   [`public_data/services/static_export.py`](../src/public_data/services/static_export.py).

```bash
cd src
# Full build (SEC network) — default curated cohort:
python manage.py publish_static_site --output ../site

# Custom cohort, with sitemap/robots for a known public URL:
python manage.py publish_static_site --tickers AAPL,MSFT,NVDA \
  --base-url https://bamr87.github.io/fredgar-ai --output ../site

# Offline re-render from already-warehoused data (no SEC calls):
python manage.py publish_static_site --skip-sync --output ../site
```

`generate_static_site` still exists for rendering arbitrary warehouse companies
(`--ticker/--cik/--all`) without any syncing.

## GitHub Pages deployment

[`.github/workflows/pages.yml`](../.github/workflows/pages.yml) builds and deploys on:

- a **weekly schedule** (Mondays 11:17 UTC — keeps the mirror fresh),
- **manual dispatch** (optional `tickers` input to publish a custom cohort),
- **pushes to `main`** that touch the static-site code, templates, or the workflow.

One-time repository setup:

1. **Settings → Pages → Build and deployment → Source: "GitHub Actions".**
2. Add a `USER_AGENT_EMAIL` repository **variable or secret** — SEC requires a contact
   email in the `User-Agent`; the workflow fails fast without it.
3. Optional: a `STATIC_SITE_APP_URL` repository variable with the public URL of the
   interactive app; every static page then shows a "Live app ↗" cross-link.
4. Optional: a `FRED_API_KEY` repository **secret**
   ([free key](https://fred.stlouisfed.org/docs/api/api_key.html)) to publish the macro
   section. Without it the build still succeeds — macro pages are simply omitted.

The published URL is `https://<owner>.github.io/<repo>/` (the workflow derives it
automatically for the sitemap). All intra-site links are relative, so the site works at any
base path — project pages, a custom domain, or `file://` on disk.

## Cross-linking the two front ends

- Static → app: `--app-url` flag or `STATIC_SITE_APP_URL` env (see
  [`src/.env.example`](../src/.env.example)); rendered in the header/footer/about page.
- App → static: set `VITE_STATIC_SITE_URL` when building the frontend; the sidebar shows a
  "Public mirror" link (see [`frontend/README.md`](../frontend/README.md)).

## Settings

| Env var | Used by | Purpose |
|---|---|---|
| `STATIC_SITE_BASE_URL` | `generate_site` | Canonical public URL → `sitemap.xml` + `robots.txt` |
| `STATIC_SITE_APP_URL` | templates | "Live app" cross-link on the mirror |
| `STATIC_SITE_SOURCE_URL` | templates | "Source" link (defaults to this repo) |
| `USER_AGENT_EMAIL` | SEC client | Required contact email for SEC fair access |
| `FRED_API_KEY` | FRED provider | Optional — enables the macro section's FRED sync at build time |

CLI flags (`--base-url`, `--app-url`) override the env vars per run.
