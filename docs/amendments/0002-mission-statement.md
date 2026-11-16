<!-- kit: governance v0.1.0 -->
# 0002 — Mission statement

- **Status:** proposed
- **Date:** 2026-11-16
- **Proposed by:** Grok Bot (agent), at the maintainer's request
- **Ratified by:**
- **Affects:** constitution §1; PRD §1.1
- **Supersedes:** none
- **Related:** [PRD.md](../../PRD.md) §1.1, §2.1, §2.3; [docs/enrichment.md](../enrichment.md); [docs/leadership-methodology.md](../leadership-methodology.md)

## Context

Constitution §1 Mission was seeded from the PRD's purpose paragraph: a description of the product, stack and roadmap, not a mission statement. The fleet governance kit expects §1 to say who the repo serves and what it is for. The maintainer asked for a mission statement that the governance model can use.

## Amendment

Replace constitution §1 Mission with:

Fredgar AI makes SEC EDGAR company data and FRED macro series queryable, reproducible and auditable, and layers optional AI on top of those sources rather than in place of them.

It serves analysts, researchers and operators who need to find, sync and join SEC filings, XBRL facts and internal company lists, and developers who integrate through the versioned API. A later hosted tier may also serve retail and prosumer investors. The product extracts and normalizes EDGAR data into a structured warehouse, optionally alongside FRED macro series, and serves it through a REST API, a React UI and a static public mirror. The structured pipeline is the system of record: every figure and enrichment claim keeps a path to its evidence, estimates are never blended with reported facts, and AI-assisted summaries stay grounded in retrieved filing text with citations.

These rules serve the PRD goals: queryable and reproducible EDGAR data, less manual work to match CRM lists to SEC issuers, and AI-assisted explanation that does not sacrifice traceability ([PRD.md](../PRD.md) §2.1). Differentiation is transparent SEC-sourced pipelines, API-first design, CRM-to-CIK workflows, and a planned AI layer on structured facts, not a black-box terminal (PRD §2.3).

_Source: [PRD.md](../PRD.md) §1.1._

## Consequences

Agents and reviewers judge fit against this mission before inventing scope. The same text is added as PRD §1.1 so the constitution's `_Source:` line stays accurate; later §1 headings are renumbered (Purpose 1.2, Scope 1.3, Version history 1.4, Stakeholders 1.5). The PRD purpose paragraph, invariants, feature catalog and AGENTS.md tagline are unchanged. Follow-ups after ratification, if wanted: align the README and AGENTS.md one-line descriptions with this wording.
