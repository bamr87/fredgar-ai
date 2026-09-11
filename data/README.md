# Data directory layout

## `reference/` (stable, app-backed)

JSON loaded at runtime (`sec_edgar.reference_data`, `data/manifest.json`).

| File | Role |
|------|------|
| `edgar_api_schema.json` | SEC company facts / submissions shapes and mapping notes. |
| `taxonomies.json` | XBRL taxonomy namespaces (`us-gaap`, `dei`, …). |
| `financial_model.json` | US-GAAP concept groups (tag preference) and derived KPI definitions. |
| `accounting_model.json` | How accounting sources merge into the canonical map. |
| `sic_codes.json` | SEC SIC master list. |
| `generated/us_gaap_account_map.json` | **Generated** — one entry per `us-gaap` concept: label, description, optional `acct_category`. |

### Enrichment reference (`reference/enrichment/`)

Loaded by `enrichment.reference` at runtime and in tests (see [`docs/enrichment.md`](../docs/enrichment.md)).

| File | Role |
|------|------|
| `iso3166.json` | ISO 3166-1 countries (iso3, UN region/subregion, centroid, currency, ccTLD, EU/OECD) and ISO 3166-2 subdivisions. |
| `business_registries.json` | Company register per jurisdiction with its GLEIF Registration Authority code and whether it has a free API, plus the legal-form → jurisdiction table. |

A legal form is a *registration fact*: "GmbH" exists because a German, Austrian or Swiss registrar created it. That makes form-vs-country checkable offline, and tells you which register to query next.

### Accounting sources (`reference/sources/accounting/`)

| File | Role |
|------|------|
| `acct_facts.csv` | Compact seed list (`us_gaap_list`, `acct_label`, `acct_description`). |
| `acct_facts_overlay.json` | JSON array with the full concept set; optional `acct_category`. Loaded **after** the CSV so it **wins** per concept. |

This replaces the older trio `acct_facts.csv` + `acct_facts.json` + `acct_facts_updated.json` (the two JSON files had identical concept keys; only the overlay file is kept).

Merge into the canonical reference file:

```bash
PYTHONPATH=src DJANGO_SETTINGS_MODULE=config.settings python src/manage.py sync_accounting_reference
```

If `generated/us_gaap_account_map.json` is missing, the loader falls back to `acct_facts_overlay.json`, then `acct_facts.csv`.

### Regenerating reference JSON from EDGAR

From the repo root (`USER_AGENT_EMAIL` set per SEC policy):

```bash
python src/manage.py generate_edgar_reference
```

Add **`--with-accounting`** to run **`sync_accounting_reference`** afterward.

## `samples/` (tracked, small)

Example rows for documentation and local experiments: CRM-style CSV, CRM sync snippet, optional `us_gaap_facts.csv`.

## `local/` (gitignored)

Place large or proprietary exports here (not committed). Examples:

- `companies-clean.json` — default path for `load_crm_companies_json`
- `companies.csv` / `companies.json` — full CRM/ERP exports
- `erp-clients.csv` / `erp-clients.json` — CRM/ERP export staging

The repo root `.gitignore` keeps `data/local/*` ignored except `data/local/.gitkeep`.


## `enrichment/`

Enrichment input lists and exported customer/vendor masters (see [`docs/enrichment.md`](../docs/enrichment.md)).

| File | Role |
|------|------|
| `master_list_v2.csv` | Input: 10,982 manufacturing suppliers (name, footprint, verticals). |
| `vendor_master_v3.csv` | Export: the golden record, with provenance and trust columns. |

Rebuild the export from the database at any time:

```bash
cd src && python manage.py enrich_export --dataset manufacturing --out ../data/enrichment/vendor_master_v3.csv
```

`hard_completeness` is the column to trust — it excludes modelled values. `revenue_basis` keeps `reported` and `estimated` apart; `unverified_website` flags the most dangerous cell in the file, because it looks exactly like a good one.
