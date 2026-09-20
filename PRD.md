# Product Requirements Document (PRD): Fredgar AI

> **How to use this document:** Product vision, roadmap, and “implemented vs planned” live here. For **architecture**, **every REST route**, and **management commands**, use the technical index at [`docs/README.md`](docs/README.md) — especially [`docs/architecture.md`](docs/architecture.md) and [`docs/api-and-cli.md`](docs/api-and-cli.md). Anything labeled *future*, *roadmap*, or *aspirational* may not exist in the codebase yet.

## 1. Document overview

### 1.1 Purpose

This PRD describes **Fredgar AI** (FRED + EDGAR, with AI; repository: **fredgar-ai**): a web-oriented system to extract, normalize, and explore **SEC EDGAR** company and filing data alongside **FRED** macro series, with a path toward **AI-assisted** interpretation and summaries. The long-term vision includes LLM-driven parsing, narrative insights, and rich visualizations; the **current product** emphasizes **direct SEC APIs**, a **structured warehouse** (companies, filings, XBRL facts, derived metrics), a **versioned REST API**, and a **React** UI.

### 1.2 Scope

| Area | Status |
|------|--------|
| **In scope (vision)** | EDGAR discovery and sync; structured financial and filing data; API and UI for search and exploration; optional macro series (FRED); future AI summaries, charts, accounts, and alerts. |
| **In scope (shipped today)** | Django + DRF backend; `sec_edgar` (SEC client, HTM ingest, submissions/facts sync); `warehouse` models and CRM staging/match flows; `public_data` + FRED; Vite/React frontend; Docker Compose; CI (Ruff, migrations, pytest, frontend build). |
| **Out of scope (near term)** | Real-time trading, brokerage integration, custom model training, non-SEC primary sources (except optional FRED and future third-party enrichments). |

### 1.3 Version history

| Version | Date | Notes |
|---------|------|--------|
| 1.0 | 2025-08-19 | Initial draft (AI-centric analyzer concept). |
| 1.1 | 2025-08-19 | User stories added. |
| 2.0 | 2026-03-28 | Aligned with implemented stack; removed duplicate sections; added implementation status and roadmap split. |
| 2.1 | 2026-09-20 | Distributed extract storage spec (incremental EDGAR/FRED cache, Kaggle + local clean snapshots). |
| 2.2 | 2026-09-20 | Bonus: Kaggle inbound identify/extract/enrich for companies, industries, markets, economies. |

### 1.4 Stakeholders

- **Product owner / development**: Core maintainers of this repository.
- **Engineering**: Backend (Django), frontend (React/TypeScript), data/SEC integration.
- **End users**: Analysts, researchers, operators matching CRM data to SEC issuers, and (eventually) retail/prosumer investors.
- **External**: SEC fair-access and `User-Agent` policy; FRED API terms when used.

---

## 2. Business goals and objectives

### 2.1 Goals

- Make EDGAR company metadata, filings, and XBRL facts **queryable and reproducible** via API and UI.
- Reduce manual work to **find, sync, and join** SEC data with internal company lists (CRM).
- Over time, add **AI-assisted** explanations and charts without sacrificing traceability to source filings.

### 2.2 Success metrics (aspirational)

Targets below apply once a hosted product and user base exist; the open-source repo is primarily **engineering-quality** driven.

- Adoption and engagement (session time, return rate) for a future hosted tier.
- **Data quality**: sync idempotency, fact coverage vs. SEC companyfacts for sampled issuers.
- **Optional AI**: when enabled, summary accuracy spot-checked against filing text.
- Qualitative feedback (NPS-style) for hosted offerings.

### 2.3 Market context

The market for financial data and filing analysis is crowded (aggregators, terminals, EDGAR mirrors). Differentiation for this product is **transparent SEC-sourced pipelines**, **API-first design**, **CRM-to-CIK workflows**, and planned **LLM layer** on top of structured facts—not a black-box terminal.

---

## 3. Target audience and personas

### 3.1 Audience

- **Analysts / operators**: Sync issuers, filings, facts; match internal company titles to SEC entities.
- **Researchers / students**: Explore metadata, filings, and facts via API or UI.
- **Developers**: Integrate via REST; run Docker or local Django.

### 3.2 Personas (unchanged themes)

1. **Alex the Analyst** — Quarterly and annual views, comparisons, accuracy and speed.
2. **Sam the Student** — Search by name, simple exploration, export for assignments.
3. **Ivy the Investor** — Ticker-first flows; later: alerts and mobile-friendly views.

---

## 4. Features and requirements

### 4.1 Implementation status (March 2026)

**Backend (`src/`)**

- **Framework**: Python 3.12+, Django 5 or 6 (see `requirements.txt`), Django REST Framework.
- **Apps**: `warehouse` (Company, Filing, Fact, sections/tables, derived metrics, CRM staging, listed issuers, EDGAR sync state), `sec_edgar` (client, parsers, sync/ingest services, management commands), `public_data` (FRED series bundles and observations), `api` (v1 routes + legacy `/api/` alias).
- **SEC**: Submissions and company facts sync; HTM filing ingest; reference JSON under `data/reference/` (schemas, taxonomies, financial model, SIC reference, accounting map); bulk and ZIP loaders where implemented.
- **API surface (examples)**: `/api/v1/companies/`, filings, facts, sections, tables, derived metrics, peer groups, company metadata, SIC reference, health, series bundles and observations; actions such as sync submissions/facts and ingest HTM where exposed on viewsets.
- **Ops**: SQLite default; PostgreSQL via `DATABASE_URL`; Docker Compose (API, Postgres, optional Vite dev, nginx static UI, CI test profile); GitHub Actions CI.

**Frontend (`frontend/`)**

- **Stack**: React 19, TypeScript, Vite; dev proxy to Django API.
- **UI**: Dashboard and company-oriented flows (metadata, EDGAR summary, exploration) as implemented in the app shell—not yet full charting or AI chat.

**Data repo (`data/`)**

- Versioned **reference** JSON under `data/reference/`; **samples** under `data/samples/`; large proprietary exports in **`data/local/`** (gitignored; see `README.md`).

**Optional / peripheral**

- **Optional AI**: Leadership narrative analyzer (`warehouse/services/leadership_ai.py`, `analyze_leadership` command / `POST /companies/{id}/analyze-leadership/`) that extracts initiatives, verbatim quotes, and direction **strictly from ingested SEC filing excerpts** into `LeadershipAnalysis`. Gated behind `ENABLE_AI_ANALYSIS` (off by default; `NoopAnalyzer` no-op), with the `anthropic` SDK as a lazy optional dependency (`requirements-ai.txt`)—not part of the core web API or PRD MVP for the Django app.

### 4.2 Roadmap: core product (from vision, not all built)

1. **Company search and selection**  
   Search by CIK, ticker, or name with autocomplete; results show name, ticker, CIK, industry/SIC where available. **Partially met** via API and UI patterns; polish and UX TBD.

2. **Data extraction**  
   10-K, 10-Q, 8-K, and other forms via submissions index and filing links; historical range; pagination. **Partially met** via sync and filing models; not all form types or UX filters are product-complete.

3. **Parsing and structure**  
   HTM parsing and XBRL fact ingestion into relational models; derived metrics and reference-driven KPI definitions. **Partially met**; full statement views (balance sheet / income / cash flow as polished reports) remain roadmap.

4. **Visualization and analysis**  
   Charts, multi-company compare, AI-generated summaries. **Future**; backend data supports stepping stones.

5. **Customization**  
   Filters by form type, date range, sections; tabular vs chart vs narrative views. **Future** (API filters exist in places; productized UI TBD).

### 4.3 Advanced / growth features (future)

- User accounts, favorites, history, dashboards.
- Export (CSV, PDF, Excel, JSON) and shareable report links.
- Alerts (new filings, thresholds).
- AI chat over retrieved facts and text (with citations).
- Collaboration (annotations, team sharing).
- Third-party enrichments (prices, news) behind explicit scope decisions.
- **Distributed extract storage** (spec: [`docs/distributed-storage.md`](docs/distributed-storage.md)): content-addressed raw EDGAR/FRED cache, revalidate-not-refetch pulls, local compressed backup, Kaggle clean snapshots.
- **Bonus — Kaggle inbound enrichment** (same spec): identify allowlisted public datasets, extract only new versions, enrich companies / industries / markets / economies as claims. EDGAR remains the identity and reported-financials source; Kaggle fills gaps (taxonomies, non-US macro, index membership) with provenance. Exercise, not MVP. Interactive app only at runtime; GitHub Pages gets the baked warehouse.

### 4.4 User flows (representative)

| Flow | Today | Target |
|------|--------|--------|
| Find company | API/UI search and metadata | Autocomplete + richer industry context |
| Sync EDGAR | Commands + API actions | One-click sync from UI with progress |
| Inspect facts | API + exploratory UI | Curated statement views and charts |
| CRM match | Staging + match commands | Guided UI workflow |
| Ask AI | Not in core web app | Chat grounded in facts and excerpts |

### 4.5 User stories (with rough status)

Format: *As a [user], I want [capability] so that [benefit].*

**Core**

1. **Alex** — Search by CIK, ticker, or name → **Partial** (API/backend; UI evolving).
2. **Sam** — Autocomplete search → **Planned** (polish).
3. **Ivy** — Fetch 10-Q / 10-K for a company → **Partial** (sync + filings; UX TBD).
4. **Alex** — AI parses filings into statements → **Future** (structured facts today; LLM narrative later).
5. **Sam** — Trends and ratios over time → **Partial** (facts/metrics; visualization TBD).
6. **Ivy** — Benchmarks and risk-style insights → **Future** (AI/analytics).

**Visualization and customization**

7. **Alex** — Interactive multi-company charts → **Future**.
8. **Sam** — Filter by form, date, section → **Partial** (API); **UI Planned**.
9. **Ivy** — Tabular / chart / narrative views → **Partial** / **Future**.
10. **Alex** — Side-by-side compare (e.g. up to 5 names) → **Future**.

**Advanced**

11–16. Accounts, export, alerts, AI chat, collaboration, third-party APIs → **Future** (see 4.3).

---

## 5. Non-functional requirements

### 5.1 Performance

- API list/detail endpoints should stay responsive under normal single-user dev and modest concurrent load; define SLOs when a hosted tier exists.
- Heavy sync and bulk jobs are **asynchronous-friendly** (management commands, background work TBD for production).
- Respect **SEC rate limits** and identify callers with `User-Agent` (`USER_AGENT_EMAIL`).

### 5.2 Security and compliance

- HTTPS in production; strong `DJANGO_SECRET_KEY` when `DEBUG=false`.
- No authentication on the open-source default app; **add authn/z** before any multi-tenant or public SaaS.
- **SEC**: Follow [SEC fair access](https://www.sec.gov/os/webmaster-faq#code-support) guidance; cache politely.
- User data (if accounts are added): GDPR/CCPA considerations; audit logging for sensitive operations.

### 5.3 Usability

- Responsive, accessible UI over time (WCAG 2.1 as target for customer-facing builds).
- Clear errors (e.g. unknown CIK, sync failures) with actionable messages.

### 5.4 Reliability

- Migration discipline and automated checks in CI.
- Backups and HA for production Postgres when deployed—not prescribed for local dev defaults.

### 5.5 Technical stack (as implemented)

| Layer | Technology |
|-------|------------|
| Backend | Django 5+, Django REST Framework, Python 3.12+ |
| Frontend | React, TypeScript, Vite |
| Database | SQLite (default), PostgreSQL (`DATABASE_URL`) |
| SEC integration | Direct HTTP APIs, `sec_edgar` client and services |
| Macro data | FRED via `public_data` (optional `FRED_API_KEY`) |
| Quality | Ruff, pytest, pytest-django, coverage gates in CI |
| Containers | Dockerfile(s), Docker Compose, optional nginx for static UI |
| Optional AI | Anthropic SDK for the leadership narrative analyzer (`ENABLE_AI_ANALYSIS`, off by default) |

---

## 6. Assumptions and dependencies

### 6.1 Assumptions

- SEC continues to offer **public data APIs** and bulk resources used by this repo.
- Maintainers can supply a valid **contact email** for `User-Agent`.
- Users of advanced features have basic finance and EDGAR literacy.

### 6.2 Dependencies

- **Runtime**: `requirements.txt`, `requirements-dev.txt`; Node.js for frontend build.
- **External**: `sec.gov` (and related); `fred.stlouisfed.org` when using FRED.
- **Reference assets**: JSON under `data/reference/` and `data/manifest.json` index.

---

## 7. Risks and mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SEC API or policy changes | Medium | High | Abstract client; document env vars; monitor SEC developer updates. |
| Rate limiting / blocking | Medium | Medium | Backoff, caching, single descriptive User-Agent. |
| XBRL / form heterogeneity | High | Medium | Tests on sampled payloads; incremental parser coverage. |
| AI hallucination (when added) | Medium | High | Ground answers in retrieved facts; citations; human review for high-stakes use. |
| Scope creep (AI vs data platform) | Medium | Medium | Keep structured pipeline as source of truth; AI as optional layer. |

---

## 8. Appendix

### 8.1 Glossary

- **CIK**: Central Index Key (SEC company identifier).
- **EDGAR**: SEC Electronic Data Gathering, Analysis, and Retrieval system.
- **MD&A**: Management’s Discussion and Analysis.
- **XBRL**: eXtensible Business Reporting Language (structured tagging in filings).

### 8.2 References

- SEC EDGAR and [developer resources](https://www.sec.gov/edgar/sec-api-documentation).
- Repository **README.md** for commands, env vars, and layout.
- Additional notes under `docs/` (e.g. EDGAR API summaries).

---

This PRD is a **living document**. Update the **implementation status** section when major capabilities ship or pivot.
