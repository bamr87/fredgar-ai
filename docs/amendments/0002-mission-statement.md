<!-- kit: governance v0.1.0 -->
# 0002 — Missions

- **Status:** proposed
- **Date:** 2026-11-16
- **Proposed by:** Grok Bot (agent), at the maintainer's request
- **Ratified by:**
- **Affects:** constitution §1; PRD §1.1, §1.5
- **Supersedes:** none
- **Related:** [PRD.md](../../PRD.md) §1.1, §2.1, §2.3; [docs/enrichment.md](../enrichment.md); [docs/leadership-methodology.md](../leadership-methodology.md)

## Context

Constitution §1 Mission was seeded from the PRD's purpose paragraph: a description of the product, stack and roadmap, not a mission statement. The fleet governance kit expects §1 to say who the repo serves and what it is for. The maintainer asked for a mission statement, then for multiple missions capped at three, then for those missions to be comprehensive and epic: Fredgar AI as the ultimate open home for all things financial. Mission 1 is the maintainer's own wording: provide data, tools, resources and transparency for all stakeholders, finance professionals and the general public. The ambition is the direction, not a claim that the work is already finished.

## Amendment

Replace constitution §1 with the following, retitled **Missions**:

Fredgar AI's direction is to become the ultimate open home for all things financial — data, tools, resources and transparency, gathered in one place that anyone can inspect and reuse.

1. **Provide data, tools, resources and transparency for all stakeholders, finance professionals and the general public.** Analysts, researchers, operators, builders, and retail and prosumer investors are first-class audiences. The aim is a shared, open commons: the same sources, the same tools, and the same trail of evidence for everyone.
2. **Make every public financial fact queryable, reproducible and auditable, and let AI explain it only with citations.** The path starts with SEC EDGAR company data and FRED macro series and widens from there. The structured warehouse is the system of record; every figure and enrichment claim keeps a path to its evidence; estimates are never blended with reported facts; optional AI stays grounded in retrieved source text rather than replacing it.
3. **Put that record in every builder's and operator's hands, and make joining private company lists to public issuers effortless and auditable.** Serve it through a versioned API, a clear interface and a public mirror, so developers can integrate anywhere and operators can match CRM lists to SEC issuers with a trail of evidence — an open toolkit for working with all things financial.

These missions set the course; they do not claim the work is finished. They serve the PRD goals in §2.1 and the differentiation in §2.3: transparent SEC-sourced pipelines, API-first design, CRM-to-CIK workflows, and a planned AI layer on structured facts.

_Source: [PRD.md](../PRD.md) §1.1._

## Consequences

Agents and reviewers judge fit against these three missions before inventing scope, treating them as the direction of the repo rather than a description of what already ships. The same text is added as PRD §1.1 so the constitution's `_Source:` line stays accurate; later §1 headings are renumbered (Purpose 1.2, Scope 1.3, Version history 1.4, Stakeholders 1.5). PRD §1.5 names the general public, finance professionals and retail and prosumer investors as first-class end users, not a later hosted-tier audience. The PRD purpose paragraph, invariants, feature catalog and AGENTS.md tagline are unchanged. Follow-ups after ratification, if wanted: align the README and AGENTS.md one-line descriptions with this wording.
