# Notes

Design essays, kept for the reasoning rather than as reference. When one of these disagrees with [`enrichment.md`](../enrichment.md) or the code, the code is right — these are dated, and they describe the framework as it stood before it moved into fredgar.

They are worth keeping because they record *why* things are built the way they are, including the bugs that forced each rule. The Eaton / Eaton Vance case in particular is the reason the website verifier exists in its current form, and it is still the clearest explanation of what an unverified value costs you.

| Note | What it argues |
|---|---|
| [Providers propose, resolution disposes](2026-09-10-enrichment-framework-providers-propose.md) | Why forbidding providers from writing to a record is the constraint everything good falls out of — auditability, contested fields, re-runnable sources. Contains the Eaton Vance bug in full. |
| [A legal form is a registration fact](2026-09-10-legal-form-is-a-registration-fact.md) | "GmbH" is itself evidence: a legal form tells you which registrar created an entity, so form-vs-country is checkable offline and routes you to the right register. |
| [Calibrate, don't guess](2026-09-10-calibrate-dont-guess.md) | Running the full list with no network, and the two bugs that only appear at scale. Also: interrogate green tests, and audit what your filter *rejects*. |
| [There is no company database](2026-09-10-open-company-data-master-list.md) | The open-data landscape as a spine (GLEIF, EDGAR) plus satellites, and what that implies for building a master list. |

These carry Jekyll front matter because they were drafted as blog posts. Nothing in the repo reads them.

## What changed once this moved into fredgar

The essays predate the port, so a few things they describe are no longer true:

- **Storage.** Claims live in Postgres/SQLite through the Django ORM (`Enrichment*` models in `warehouse`), not in a standalone SQLite file.
- **The revenue model.** "Order-of-magnitude placeholders" for revenue-per-employee were replaced by a benchmark derived from the SEC filers in the list itself, with its sample size carried in every estimate.
- **EDGAR and FRED are providers now**, not future work — `edgar_issuer`, `edgar_submissions`, `edgar_facts`, `fred`, `fred_deflator`.
- **GLEIF is not implemented.** It is still the highest-value addition for the non-US majority of any list, and `jurisdiction` already tells every record which register to query.
