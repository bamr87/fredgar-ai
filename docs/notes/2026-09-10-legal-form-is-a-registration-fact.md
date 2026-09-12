---
title: "A Legal Form Is a Registration Fact"
date: 2026-09-10
categories: [data-engineering, master-data, open-data]
tags: [entity-resolution, iso3166, gleif, company-registry, validation, geocoding]
excerpt: "Validating 10,982 companies against public business registers with no network access — by noticing that 'GmbH' is itself evidence."
---

## The constraint

Validate ten thousand companies against public business registers. No outbound HTTP — the environment blocks everything.

That looks like a stopper. It isn't, because of one observation:

> **A legal form is a registration fact.**

"GmbH" exists because a German, Austrian or Swiss registrar created it. "Sdn Bhd" because a Malaysian one did. "S. de R.L. de C.V." is Mexican. The suffix on a company name is not decoration — it is a trace of the registration event that brought the entity into being. And you can check it offline.

So a record whose legal form and stated country disagree gets flagged before any network call, and the same table tells you *which register* to query when you do have a network.

## Building the reference

Three build-time dependencies, zero runtime dependencies. `pypi` was reachable even though the open web was not, so:

- **pycountry** — ISO 3166-1 (249 countries) and 3166-2 (5,046 subdivisions)
- **country_converter** — UN region, continent, EU and OECD membership
- **countryinfo** — centroids, capitals, ccTLDs, currencies

A generator script flattens all three into one embedded Python module. The framework stays dependency-free at runtime; regenerating is one command.

```
coverage: centroid 236 | un_region 247 | tld 236  / 249 countries
subdivisions: 5,046 across 200 countries
```

One trap worth naming: I first emitted that table with `json.dump`. JSON writes `true` and `false`; Python wants `True` and `False`. The generated module failed to import on line 20. `pprint.pformat` emits valid Python literals — use it when generating code, not JSON.

Result across all 10,982 records: **99.7% ISO-normalized** — alpha-2, alpha-3, UN region and subregion, centroid, currency, ccTLD, EU/OECD flags. Four failures, all the string `"Macedonia"`.

## What validation actually found

| Verdict | Records | Share |
|---|---|---|
| Jurisdiction consistent | 1,924 | 17.5% |
| **Jurisdiction conflict** | **203** | **1.8%** |
| Unknown (no usable form) | 8,847 | 80.6% |

Plus registry routing for every record: **65% sit in a jurisdiction whose national register has a free API** — Companies House, SIRENE, Brønnøysund, CVR, PRH, ARES, KRS, ABR, Receita Federal.

## Three bugs, each found by auditing output rather than reading code

### 1. Ambiguity leaking through decomposition

The first run flagged 364 conflicts. Grouping them by form token immediately looked wrong:

```
120  corporation
 40  gmbh
 29  plc
```

`corporation` is a generic English word used by companies on every continent. It was not in my ambiguous-forms set, but my composite decomposer split it to `corp`, which *was* — and inherited `corp`'s jurisdictions. **129 of 364 flags, a third of the review queue, were false positives.**

### 2. Over-correcting, and breaking the good cases

The obvious fix — treat any token *starting with* an ambiguous root as ambiguous — broke `sarl`, because "sarl" starts with "sa". It would have broken every legitimate long form beginning with two ambiguous letters.

The correct rule distinguishes known from unknown:

```python
if t in LEGAL_FORM_JURISDICTION:
    return t in AMBIGUOUS_FORMS       # an exact key is judged on its own merits
parts = _decompose(t)
return (not parts) or all(p in AMBIGUOUS_FORMS for p in parts)
```

### 3. My reference data was parochial

Grouping the remaining flags by *country* rather than by form:

```
sarl flagged in: DZ(20), US(2), MX(1), TN(1)
spa  flagged in: US(5), GB(3), DZ(3)
```

Twenty Algerian SARLs. SARL and SPA are standard across the Maghreb and francophone Africa — my table knew only metropolitan France. Those were not bad records; they were a bad reference table confidently marking real companies as suspect.

Review queue after all three fixes: **364 → 203**, every removal a false positive. The survivors are genuine: GmbH entities listed in China, `plc` in the US, `B.V.` in Poland.

## The bug the validation itself exposed

`Akzo Nobel Nederland BV` resolved to **Great Britain**.

The adapter took the first listed country as headquarters. But an operational list orders countries by site count, not by domicile — and the list had already discarded everything after the first entry at ingest, so nothing downstream could recover the Netherlands.

The fix keeps the whole footprint and adds an inference provider: if the form is `B.V.` and the Netherlands appears anywhere in the footprint, that is where the registrar sits. 33 headquarters corrected — ASSA ABLOY AB → SE, Brose Fahrzeugteile GmbH → DE, Henkel AG & Co. KGaA → DE, Metalsa S.A. de C.V. → MX.

**The validation layer found a bug in the ingestion layer.** That is what validation is for, and it only worked because the check was independent of the thing it was checking.

## Confidence must track specificity

My first version marked those inferences `verified=True`. That was wrong twice over.

`Eaton Corporation plc` is Irish-domiciled. `plc` spans seven jurisdictions across two continents, Eaton has no Irish site in this list, so the rule proposes GB — better than "United States", still not right. Meanwhile `KGaA` narrows to Germany alone and is right every time.

So confidence scales with how much the form actually narrows things:

```python
conf = 0.85 if len(juris) <= 3 else (0.70 if len(juris) <= 5 else 0.55)
```

And nothing here is ever `verified` — no register has confirmed it. It is a defensible inference from a registration fact, and any real registry lookup must be free to outrank it. After the change, the 0.85 tier is correct across the board and the shaky `plc` cases sit at 0.55 where they belong.

## The framework hole this uncovered

Deleting a provider's claims to re-run it did **not** remove its effects. The record's `fields` blob accumulated promoted claim values, so the corrected run read the very state it was meant to replace — `Lear Corporation` still carried `legal_form_token='corporation'` with no backing claim anywhere.

The design principle was "providers propose, resolution disposes." A cache that outlives its claims quietly violates it. The fix splits immutable input from derived cache:

```sql
seed   TEXT   -- what the input list said; never changes
fields TEXT   -- derived cache, rebuilt from claims on every load
```

`load_record` now reconstructs from seed plus *current* claims. Delete a provider's claims and its contribution disappears — which is what makes re-running a fixed provider actually re-run it.

**Derived data must be derived.** Any cache you can mutate independently of its source will eventually disagree with it, and disagree silently.

## Honest geography

Every row has coordinates. Every row's coordinates are a **country centroid** — which is why the column sits next to `geo_precision`, and why centroids are excluded from the trustworthy-completeness score. A centroid is an honest coarse answer; a centroid presented as an address is a lie with a decimal point.

## Working with AI on this

**Group your flags before you trust them.** One `GROUP BY` on form token exposed `corporation` as a third of the review queue. A second `GROUP BY` on country exposed the Algerian gap. Neither is visible in the aggregate "203 conflicts" number, and neither required reading a line of code.

**Check the fix as hard as the bug.** My ambiguity fix worked for `corporation` and silently broke `sarl`. Print the whole matrix — the cases that should change *and* the cases that shouldn't — every single time.

**Independence is what makes validation work.** The Akzo Nobel bug was in ingestion, found by a check that knew nothing about ingestion. A validator that shares assumptions with the thing it validates confirms them instead of testing them.

**"Verified" is a promise.** Reserve it for things something external actually confirmed. An inference labelled as a verification corrupts every precedence rule downstream, and it does so invisibly.

---

*10,982 records: 99.7% geographic coverage, 203 flagged for review, 33 headquarters corrected, 15 regression tests — all with no network access.*
