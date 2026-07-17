# Leadership & stakeholder analytics — methodology and responsible use

This Fredgar AI subsystem extracts company leadership from SEC filings and computes a transparent "stakeholder orientation" (people-vs-profits) signal. **Read this before relying on any output.**

## What it is — and is not

- It **is** a way to (a) list officers/directors/owners disclosed in SEC filings and
(b) summarize, with fully disclosed inputs, whether a company's capital allocation over a period leans toward **reinvestment** (capex, R&D) or **shareholder payout** (buybacks, dividends).
- It is **not** an approval rating, a popularity score, a personality/competence
judgment of any named individual, an endorsement, or investment/HR/financial advice. Signals describe **company behavior over a period**, not a person's character.

Every score decomposes into its source XBRL concepts and periods. Always verify material conclusions against the original filings (linked throughout).

## Data sources

| Source | Used for | Status |
|--------|----------|--------|
| SEC **Forms 3/4/5** (ownership) | Officer/director/owner roster, titles, role flags, tenure bounds, insider buy/sell | **Implemented** — legally public, parsed from EDGAR |
| SEC **XBRL facts** (10-K/10-Q) | Capex, R&D, buybacks, dividends, revenue → orientation signals | **Implemented** |
| Filing **text** (bios, human-capital, MD&A) | Quotes, initiatives, narrative | Foundation present (filing corpus + chunks); narrative extraction is the AI path below |
| **Earnings call transcripts** | Quotes, forward direction | **Not scraped.** Not on EDGAR and usually copyrighted/paywalled — ingest only user-supplied/licensed transcripts |
| **LinkedIn / third-party profiles** | Background enrichment | **Not scraped** (ToS/privacy). A pluggable `external` enrichment field on `Person` accepts licensed/manual data only |

## The orientation index (method v1.0)

`orientation_index` ∈ roughly [−1, +1], a weighted average of the **available** signals (missing signals are excluded and disclosed). Latest full-year (~annual) facts are used.

| Signal | Definition | Weight |
|--------|------------|--------|
| `allocation_balance` | `(capex + R&D − buybacks − dividends) / (capex + R&D + buybacks + dividends)` | 0.40 |
| `capex_intensity` | `capex / revenue`, scored vs a 5% reference — a **local/physical-investment proxy** | 0.25 |
| `rnd_intensity` | `R&D / revenue` — capability/people investment | 0.20 |
| `insider_alignment` | Net Form 4 acquired(+)/disposed(−) across leadership — directional "skin in the game" | 0.15 |

Label: `index ≥ 0.33` → "Reinvestment / stakeholder-tilted"; `≤ −0.33` → "Payout / shareholder-tilted"; otherwise "Balanced".

### Known limitations (important)
- **Outsourcing/offshoring is not directly observable** from XBRL. `capex_intensity` is
only a *proxy* for building physical/local capacity. True outsourcing signals require geographic-segment disclosures or the text/AI path — not this index.
- **`insider_alignment` counts all Form 4 share changes**, including option exercises,
grants, and tax withholding — not just open-market conviction buys. A refinement would weight by transaction code (P/S vs A/F). The raw value is always disclosed.
- **Employee-count / wage signals** are omitted because there is no reliable, universal
  us-gaap XBRL tag for them; add them when a company's human-capital data is structured.
- Tenure (`first_seen`/`last_seen`) is a **filing-date range**, not an official
  appointment record.

## AI analysis (Claude by default, grounded)

Narrative extraction — leadership **initiatives**, **verbatim quotes**, and **stated forward direction** — runs through a pluggable analyzer with **Claude as the default provider** (`ENABLE_AI_ANALYSIS=true`). It stays **purely additive**: it degrades to a no-op unless the optional `anthropic` SDK *and* a credential are present, so the structured, source-cited signal above is always the default output and a credential-less checkout makes no API calls.

**How it stays grounded.** When enabled, the analyzer (`AnthropicAnalyzer`, default model `claude-opus-4-8`) is sent *only* excerpts from this company's already-ingested SEC filing text, each labeled `[S1]`, `[S2]`, …, and is constrained by a strict system prompt to:

1. Ground every item in the excerpts and cite the source label.
2. Reproduce quotes **verbatim** — never invent, paraphrase, or reconstruct a quote; if no
   verbatim quote exists, return none.
3. Make **no** personal, character, competence, popularity, or "approval" judgment about any
   named individual — only disclosed company/leadership actions and plans.
4. Use no outside knowledge and no speculation.

Output is validated against a JSON schema (structured outputs), persisted as a `LeadershipAnalysis` row with the `used_sources` it cited, and degrades gracefully: if the analyzer is off (or no credential/SDK is configured), no filing text is available, or the model call fails, a clearly-marked empty/`error` result is returned and stored — never a fabricated one.

**Auth & setup.** AI analysis is on by default; you only need the SDK and a credential to make it live. Authentication is **token-first** — a Claude Code OAuth token is preferred and sent as a Bearer token (with the `oauth-2025-04-20` beta header); an API key is the fallback. Set **only one** — the API returns 401 if both are present.

```bash
pip install -r requirements-ai.txt                    # installs the optional `anthropic` SDK
export CLAUDE_CODE_OAUTH_TOKEN=$(claude setup-token)  # preferred: Claude Code OAuth token
# or, instead of the token:
# export ANTHROPIC_API_KEY=sk-...                     # fallback: metered API key
# ENABLE_AI_ANALYSIS defaults to true; AI_ANALYSIS_MODEL defaults to claude-opus-4-8
```

This is narrative extraction with citations, **not** an opinion about people, and not investment/HR advice. Always verify quotes and initiatives against the cited filings.

## Commands & API

```bash
python manage.py sync_leadership --ticker TSLA --limit 25          # extract officers/directors
python manage.py compute_stakeholder_assessment --ticker TSLA     # compute the index
python manage.py analyze_leadership --ticker TSLA                  # LLM narrative (Claude; see above)
```

- `GET /api/v1/companies/{id}/leadership/` — roster with titles, roles, tenure, net insider shares
- `GET /api/v1/companies/{id}/stakeholder-assessment/` — index + decomposed signals + caveats
- `GET /api/v1/companies/leadership-compare/?cik=…&cik=…` — compare leadership + orientation across companies
- `POST /api/v1/companies/{id}/analyze-leadership/` — run the LLM narrative analysis (admin only)
- `GET /api/v1/companies/{id}/leadership-analysis/` — latest stored narrative analysis (with caveats)

The static site renders a **Leadership** table and a **Stakeholder orientation** section (index, signal breakdown, and these caveats) on each company page, with CSV/JSON export. When a grounded AI analysis exists, it also renders a **Leadership analysis (AI)** section (summary, initiatives, verbatim quotes with source labels, and the AI caveat).
