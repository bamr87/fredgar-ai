# Fredgar AI — frontend

React 19 + TypeScript + Vite UI for the Django API in the repo root.

## Scripts

```bash
npm install
npm run dev      # dev server (default http://127.0.0.1:5173)
npm run build    # production bundle to dist/
npm run preview  # serve dist locally
npm run lint     # ESLint
```

## API and proxy

- **Local dev:** Vite proxies `/api` to the backend (default `http://127.0.0.1:8000`, override with `API_PROXY_TARGET`). Start Django from `src/` (`python manage.py runserver`) first.
- **`VITE_API_BASE`:** Set in `.env` or `.env.local` to prefix all API URLs (e.g. `https://api.example.com`). Omit trailing slash. When unset, requests use same-origin paths like `/api/v1/...` (works with the proxy or nginx same-origin deploy).
- **SEC `User-Agent`:** The backend must send a contact email to SEC. The UI can supply it per browser via `localStorage` or `VITE_SEC_USER_AGENT_EMAIL`; see [`src/lib/http.ts`](src/lib/http.ts) (`X-Sec-User-Agent-Email` header).
- **`VITE_STATIC_SITE_URL`:** Public URL of the statically generated mirror (GitHub Pages). When set, the sidebar shows a "Public mirror" link; see [`docs/static-site.md`](../docs/static-site.md).

Copy [`frontend/.env.example`](.env.example) if you need a template.

## App routes

| Path | Screen |
|------|--------|
| `/` | Dashboard (`Dashboard`) — company search, recently viewed companies, coverage facets, quick links, industry/HQ breakdowns |
| `/companies` | Company explorer table (`CompanyExplorer`) |
| `/companies/:id` | Single company detail (`CompanyDetail`) — overview, financials, filings, facts, leadership tabs; Overview and Financials open with a financial-highlights card (latest XBRL facts, compact values with full precision on hover, derived margins and debt/equity), and the Financials trend has a period-over-period change table |
| `/search` | Full-text filing search (`FilingSearch`) |
| `/compare` | Cohort comparison (`Compare`) |
| `/peers` | Peer groups (`PeerGroups`) |
| `/macro` | Macro time series (`Macro`) |
| `/settings` | Settings (`Settings`) — auth token, SEC contact email, theme |
| `/explore`, `/metadata` | Redirect to `/companies` |

## Layout

- [`src/App.tsx`](src/App.tsx) — route table (lazy-loaded pages)
- [`src/layout/AppShell.tsx`](src/layout/AppShell.tsx) — sidebar nav, global search, theme toggle, backend-readiness indicator
- [`src/lib/api.ts`](src/lib/api.ts) — typed fetch helpers for `/api/v1/`; [`src/lib/http.ts`](src/lib/http.ts) — base fetch, auth token + SEC email headers
- [`src/lib/format.ts`](src/lib/format.ts) — display formatters (compact money, per-share, full-precision tooltips, unit labels); [`src/lib/finance.ts`](src/lib/finance.ts) — KPI concept chains, client-side margins/ratios, period-over-period change
- [`src/pages/`](src/pages/) — one module per route (e.g. `Dashboard.tsx`, `CompanyExplorer.tsx`, `CompanyDetail.tsx`), with company detail tabs under [`src/pages/company/`](src/pages/company/)

Project-wide docs: [../docs/README.md](../docs/README.md), [../README.md](../README.md).
