---
title: "There Is No Company Database. There Is a Spine and Some Satellites."
date: 2026-09-10
categories: [data-engineering, open-data, ai-assisted-development]
tags: [entity-resolution, gleif, sec-edgar, wikidata, mcp, etl, sqlite]
excerpt: "Building a master company list from 11,000 messy names and only open data — and why the MCP server you want is the one pointed at your own database."
---

## The question

I had a CSV: 10,982 manufacturing company names, 16,193 sites, a scattering of countries and verticals. The question I started with was the obvious one:

> What is an open, public, comprehensive tool or dataset I can connect via MCP to
> search and extract company data?

The honest answer is that it does not exist. Not as one thing. What exists is a **spine** and some **satellites**, and knowing which is which saves you weeks.

## The spine: GLEIF

The [Global Legal Entity Identifier Foundation](https://www.gleif.org/en/about/open-data) publishes the LEI register under **CC0** — genuine public domain, no key, no registration, full bulk download. Roughly 2.9 million legal entities worldwide.

What makes it the spine rather than just another source is *Level 2 data*: "who owns whom." Direct parent and ultimate parent, as declared by the entity itself. Corporate hierarchy is the single hardest thing to buy and GLEIF gives it away.

What GLEIF does **not** have: revenue, employees, industry codes. It tells you *who exists and who owns them*. Nothing about how big they are.

## The satellites

| Need | Source | Licence | Reality check |
|---|---|---|---|
| US financials | SEC EDGAR XBRL | public domain | Complete, free, no key. 10 req/s, real User-Agent enforced. |
| UK financials | Companies House | OGL | Even small-company accounts. Genuinely excellent. |
| Employees, industry | Wikidata | CC0 | One SPARQL query, all orgs with an LEI. Large caps only. |
| Registry breadth | OpenCorporates | gated | 200M+ entities but the API is no longer meaningfully open. |
| Size benchmarks | Census CBP / Eurostat SBS | public | Revenue-per-employee by NAICS/NACE. The private-company workhorse. |

GLEIF also publishes a free [OpenCorporates→LEI mapping](https://www.gleif.org/en/lei-data/lei-mapping/download-oc-to-lei-relationship-files) covering over half the LEI population, updated fortnightly. Free bridges between open datasets are worth more than most paid enrichment.

## The insight that actually mattered

I asked for an MCP server. That was the wrong shape for the problem.

**MCP is a request/response interface for an agent working interactively.** It is excellent when you want to ask about one company, right now, in conversation.

Eleven thousand companies across four sources is not that. It is batch ETL, and batch ETL needs rate limiting, checkpointing, retries, idempotence, and somewhere to put answers that disagree with each other. None of that belongs in a tool call.

The right architecture inverts it:

```
open sources → batch pipeline → your database → MCP server → agent
```

Run the pipeline. Point MCP at the **result**. Now your agent answers from a local index in milliseconds instead of re-fetching the internet, and your enrichment logic lives somewhere you can test it.

For the interactive half, `companyscope-mcp` aggregates twelve keyless sources, and there are solid `sec-edgar-mcp` and `gleif-mcp-server` implementations.

## Bulk beats loops, by orders of magnitude

The naive design is a loop: for each of 11,000 companies, call the API. At a polite 5 requests/second that is roughly 37 minutes per source, and you will be rate-limited or blocked long before you finish.

GLEIF publishes a concatenated file of the entire register. **One HTTP request against 2.9 million entities**, then an offline join. The correct pattern is almost always: download the reference set once, index it by a blocking key, join locally, and reserve per-row API calls for the small set where precision justifies the cost.

Same for SEC — `company_tickers.json` is every registrant in one file. Same for Wikidata — one SPARQL query returns every organization carrying an LEI.

## Five design decisions worth stealing

**1. Tier before you enrich.** Not every row deserves an API call. I scored each company by site count and country spread:

- Tier 1 (423 companies, ≥5 sites or ≥3 countries) — per-company API lookups
- Tier 2 (6,551) — bulk-file matching only
- Tier 3 (4,008) — single site, no legal form. Parked.

Tier 3 is mostly *facility labels*, not companies. Chasing them does not find data, it manufactures wrong matches.

**2. Separate identity from facts.** The master table holds identity only. Every enriched fact lives in a narrow table with `source`, `confidence` and `retrieved_at`. This is what lets you re-run a source, disagree with it, or drop it entirely without rebuilding the list.

**3. `basis` is not decoration.** `reported` came from a filing. `estimated` came from a model whose inputs are named in a `method` string:

```
model:rev_per_head_v1[vertical=Industrial;factor=1.0;employees=sites*180]
```

They never share a column. A revenue figure you cannot trace is worse than a blank, because a blank does not get pasted into a board deck.

**4. Ambiguity is an answer.** When two candidates score within 0.02 of each other, the row resolves to `ambiguous` — not to the higher score. Silent wrong matches are the failure mode that destroys trust in a master list, and they are invisible until someone important notices.

**5. Mine the list before you leave it.** Before spending a single API call, I matched the list against *itself*. A facility list contains the same corporate group many times over. That found **750 subsidiary→parent links for free** — Atos with 25, Avery Dennison with 22, Unilever with 20.

## Four bugs, and what they teach

The interesting part of the session was not the architecture. It was the bugs.

**Legal forms are not universal.** My first suffix-stripper handled `Inc`, `GmbH`, `Ltd` — the Anglo-European defaults. Then I audited the *parked* tier and found 274 instances of `de`, 87 of `r.l`, 86 of `c.v`. Mexican `S. de R.L. de C.V.` Brazilian `Ltda`. Malaysian `Sdn Bhd`. Indonesian `PT` and `Tbk`. Japanese `K.K.` Real companies, silently discarded because my list was parochial.

*Audit what your filter rejects, not what it accepts.* The rejects are where the bias lives.

**Comparing incompatible representations, silently.** I scored country agreement between registry data (ISO-2: `IE`) and an operations list (English: `United States`). `"IE" == "UN"` is always false, so *every* candidate got a mismatch penalty and nothing crossed threshold. Zero matches, no error, no warning.

The second-order lesson was better. Once I fixed the comparison, Eaton *still* mismatched — because Eaton Corporation plc is Irish-domiciled with its operational HQ in Ohio. Both values were correct. So country agreement became a **tiebreaker that can never veto a name match**, which is what it should have been all along.

**A primary key that silently discards data.** My attribute table was keyed `(company_id, key, source)`. Eaton has five verticals. Four of them vanished into an `INSERT OR REPLACE`, and Eaton got classified "Life Sciences" — technically a row it had, semantically nonsense.

Attributes are frequently multi-valued. Put the value in the key, and add an `ordinal` so "primary" stays answerable.

**A test that proved nothing.** I built decoys — `Easton Industries`, `Eaton Vance Corp`, `Lear Capital` — ran the matcher, got 5/5 correct and 0 false positives, and nearly moved on. Then I checked *why*: every decoy had landed in a different blocking key. The blocking was so effective the decoys never reached the scoring logic. My ambiguity rule was completely untested.

I wrote a fixture with two genuinely colliding entities. It passed. But it passed *for a reason I had verified*, which is the only kind of passing that counts.

## Working with AI on this

**Give it the real data immediately.** Every one of those four bugs surfaced from running against the actual 10,982-row file. None would have appeared in a synthetic fixture, because synthetic fixtures encode the assumptions you already have.

**Ask "why did that pass?" as often as "why did that fail?"** The decoy test is the sharpest example. A green result that you have not explained is a result you do not have.

**Environment constraints are information.** The egress policy blocked GLEIF and SEC in both my sandbox and my local shell. Rather than a dead end, that forced the matching logic to be testable *offline against fixtures* — which is a better design than one that can only be exercised against a live API.

**Let it audit its own output.** The most valuable single command of the session was counting the most common short tokens among *parked* rows. That is a five-line diagnostic that found an entire class of missing legal forms. Ask for the histogram of what got rejected.

## Where it landed

```bash
python cli.py init     --db master.db --csv companies.csv
python cli.py selflink --db master.db     # 750 parent links, no network
python cli.py gleif    --db master.db --bulk gleif_golden.csv
python cli.py edgar    --db master.db
python cli.py wikidata --db master.db
python cli.py estimate --db master.db
python cli.py export   --db master.db --out master_list.csv
```

Pure standard library, SQLite, resumable at every stage. The enrichment sources are open, the estimates are traceable, and the ambiguous rows are labelled rather than guessed.

The master list is not the deliverable. **The pipeline that rebuilds it next quarter is the deliverable** — because company data goes stale, and a list you cannot regenerate is a snapshot pretending to be an asset.

---

*Sources: [GLEIF Open Data](https://www.gleif.org/en/about/open-data) · [GLEIF Level 2](https://www.gleif.org/en/lei-data/access-and-use-lei-data/level-2-data-who-owns-whom) · [SEC EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) · [Wikidata SPARQL](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service)*
