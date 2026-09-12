---
title: "Calibrate, Don't Guess: Running an Enrichment Framework at Full Scale"
date: 2026-09-10
categories: [data-engineering, testing, ai-assisted-development]
tags: [entity-resolution, master-data, calibration, metrics, python]
excerpt: "Running 10,982 records through an enrichment framework with no network access — and finding two bugs that only appear at scale."
---

## The run

10,982 manufacturing companies, through a provider framework, end to end:

```
INGEST              10,982 records, 0 duplicates          0.7s
domain_guess        44,892 candidates across 10,965      12.6s
selflink               750 subsidiaries -> 280 parents   14.6s
model               10,982 revenue estimates              (same pass)
resolve             23,447 golden fields                  1.0s
                    57,374 claims total, 0 errors
```

Then the part I could not run: **zero websites verified**, because both the container and the linked machine sit behind a blanket egress block. That constraint produced the two most useful findings of the session.

## Bug one: a completeness metric that was itself incomplete

The MDM export carries a `completeness` score — the headline "can I trust this row?" number. After the full run it read **0.0–0.1 for all 10,982 records**, while `legal_name` and `revenue_estimated` were both 100% populated.

The weights were keyed on internal provider field names:

```python
COMPLETENESS_WEIGHTS = {"revenue": 2.0, "parent_lei": 1.5, ...}
```

The export columns were named `revenue_estimated` and `parent_name`. The names had drifted apart, nothing referenced both, and the score silently summed to near zero. Every row looked untrustworthy, including the ones that weren't.

Two changes. Key the weights on **export column names**, and score the **assembled row** rather than the golden table. Then add a guard that makes the drift impossible to reintroduce:

```python
missing = [k for k in COMPLETENESS_WEIGHTS if k not in EXPORT_COLUMNS]
```

It immediately caught a second instance — `phone` was weighted but never exported. A three-line assertion found a bug I had shipped ten minutes earlier.

**If a metric can go wrong quietly, something must assert its inputs exist.** Metrics fail silently by nature: nobody gets a stack trace from a number that is merely wrong.

## Bug two: what the live web taught the matcher

I could not fetch pages from code, but I could fetch a handful by hand. So I drew a stratified sample of 20 across the three tiers, took the domains the heuristic had guessed, and checked what was actually there.

Two immediate results. First, the guesses themselves were revealing:

```
Custom Mold & Design       -> custom.com
Zhejiang Yinzuo Cases      -> zhejiang.cn
United Bakeries a.s.       -> united.cz
Integral Access Inc.       -> integral.com
```

Taking a bare first token as a domain stem works for `endologix` and fails completely for `custom`, `united`, and a Chinese province. Those now require the lead token to be distinctive — not a descriptor, not a place, at least five characters. `custom.com`, `zhejiang.cn` and `united.cz` stopped being generated.

Second, and more valuable, **a false negative I would never have invented**:

```
list name:  Liebherr-International SA
site says:  Liebherr Group
verdict:    REJECTED  (name agreement 0.25)
```

Both are Liebherr. My coverage rule demanded that ~all tokens of the company name appear on the page, and `international` did not. But list names carry legal-entity detail that brand sites drop — this is not an edge case, it is the normal relationship between a registry name and a homepage.

The fix measures coverage over **distinctive tokens only**, ignoring descriptors on *both* sides:

```python
dist_A = {t for t in A if t not in DESCRIPTORS} or A
cov_want = len(dist_A & B) / len(dist_A)
```

`Liebherr-International SA` vs `Liebherr Group` → 1.0. And critically, the adversarial cases still reject: `Eaton` vs `Eaton Vance` and `Lear Corporation` vs `Lear Capital` are blocked by the *distinctive extra token* rule, which is separate and unaffected.

The five hand-checked pairs are now permanent regression tests, with the date they were measured and a comment explaining what each one caught.

## The number I refused to produce

The obvious next move is a headline hit rate. "The framework resolves X% of your list." I had five scoreable data points and the verifier got all five right, which is a tempting 100%.

That number would have been worthless. Five is not a sample, and the stratified draw skewed toward recognizable multinationals — Merck and Liebherr are not representative of nine thousand single-site suppliers.

So I computed something that *does* generalize, because it is structural rather than sampled:

| Name shape | Records | Share |
|---|---|---|
| Distinctive multi-token | 8,097 | 73.7% |
| Single token | 2,321 | 21.1% |
| Generic or place lead word | 564 | 5.1% |

This is not a hit rate. It is the **distribution of difficulty**, computed over every record, and it says something real: 74% of the list has names the guess path handles well, 21% are single-token names that only an exact domain echo can verify, and 5% will mostly miss. That is enough to size a search budget without pretending to a precision I do not have.

**Report the thing you measured, at the confidence you measured it.** A range you can defend beats a point estimate you cannot.

## What "run it on everything" means when you can't

Roughly 60% of the enrichment work needed no network at all, and it ran across the entire dataset in about 40 seconds:

- Name normalization and blocking keys
- 44,892 domain candidates
- 750 subsidiary→parent links, from the list against itself
- 10,982 revenue estimates, every one flagged `basis=estimated`
- Golden resolution across 57,374 claims

The remaining work is checkpointed and resumable. Every attempt is recorded in `provider_run`, so handing over the SQLite file and a runbook is a complete handoff — the next run picks up exactly where this one stopped, and re-running costs nothing for work already done.

That property is worth designing for deliberately. **An enrichment run should be something you can stop in the middle and give to somebody else.**

## Working with AI on this

**Constraints are a research method, not just an obstacle.** No network forced hand-verification of a small sample, which surfaced the Liebherr false negative. An automated run would have recorded it as one more unresolved row among thousands, and I would never have looked.

**Ask what a green number is made of.** `completeness: 0.05` across 10,982 rows looked like an honest reflection of an unfinished run. It was a key-name bug. The question that found it was "why is legal_name 100% but completeness near zero?" — noticing that two numbers on the same screen could not both be right.

**Sample the output, not just the code.** Printing 20 actual guessed domains next to their company names took one command and exposed a whole failure class. Unit tests confirm the behavior you thought of; looking at real output shows you the behavior you didn't.

**Push back on your own convenient numbers.** The 100%-on-five-cases result was right there and would have looked great. Structural distribution over all 10,982 is less flattering, more useful, and actually true.

---

*Framework state: 57,374 claims, 0 errors, 7 passing tests including live-web calibration pairs. The network half is a runbook away.*
