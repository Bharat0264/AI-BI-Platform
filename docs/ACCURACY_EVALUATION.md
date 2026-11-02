# Phase 6: Independent analytical evaluation

Implemented and executed locally on 2 November 2026. No commit, push or deployment performed.

**Result: 262/332 synthetic cases passed; 70 failed. All 173 returned answers to answerable cases matched the independent arithmetic reference. Overall answerable-case coverage was 71.2%.**

The remaining failures are preserved in the report, not relabelled as safe refusals. This does not establish real-world accuracy, usability, novelty or competitive superiority.

| Test family | Cases | Before passed | After passed |
|---|---:|---:|---:|
| adversarial | 12 | 7 | 12 |
| ambiguity | 10 | 10 | 10 |
| ordinary_phrasing | 80 | 10 | 10 |
| safe_refusal | 70 | 70 | 70 |
| supported_arithmetic | 160 | 160 | 160 |

## What changed

- Added an arithmetic oracle using Python Decimal and independent grouping loops. It does not reuse pandas aggregation, engine evidence verification or the engine's answer status as proof of correctness.
- Added a frozen 332-case evaluation: 160 supported-arithmetic cases, 70 expected safe refusals, 10 ambiguity cases, 80 ordinary-phrasing capability cases and 12 adversarial fixtures. Ten seeded tables underlie repeated templates; cases are correlated, not independent statistical samples.
- Kept the same case IDs, generation code and scoring code for the before/after runs. The raw reports include source hashes, seeds, package versions, Git SHA, latency, expected values, actual evidence and failures.
- Corrected the legacy benchmark's numeric metric. It now compares answerable questions with independently computed values; unsupported questions no longer count as correct numeric answers. Free-form provider output is NOT_EVALUATED rather than assigned a fabricated numeric score. The benchmark no longer reruns every question merely to count repair attempts.
- Fixed five analyst safety gaps exposed by the adversarial cases: percentage-labelled revenue interpreted as an amount, boolean amounts, mixed currencies, missing currency labels, and distinct grouping labels collapsing to the same JSON text key.
- Monetary questions now require one consistent supplied currency code when an explicitly named currency column is present. That column is included in evidence scope and the observed code is recorded in the definition. Quantity totals do not require currency conversion.

## Before and after

- Passed cases: 257 → 262 of 332.
- Unsafe unconditional answers on ambiguity/refusal cases: 5 → 0.
- Answerable requests: 243; returned answers: 173; independently correct returned answers: 173.
- Ordinary-phrasing cases answered correctly: 10 of 80 (12.5%).
- Unexpected exceptions: 0.

The count of safe refusals is a policy/scope check: requests for unsupported periods, predictions, causal explanations and filters are expected to refuse until those operations have an executable plan. That is different from claiming the underlying business question is fundamentally unanswerable from data.

Percentage and boolean fixtures test whether they can safely stand in for a business amount without an explicit formula. The result is not a claim that percentages or booleans can never be aggregated for other purposes.

## Remaining coverage failures

The system still rejects seven of the eight ordinary-language phrasing templates across ten seeds. Examples include:

- How much revenue did we earn?
- Show me revenue for each region
- Give me the average revenue per region
- Which region earned the most revenue?

These are manually labelled answerable tasks, so their refusals count as failures. The working alternative `Show the sum of revenue` is counted as a success. This is a known grammar limitation, not a lack of numerical data. Improving intent parsing without silently swallowing filters or periods is the next development priority.

## Validation

- Full regression suite: **120 passed in 27.15 seconds**, including the existing 7 real-browser tests and 12 new oracle/safety/evaluation cases.
- Tests deliberately corrupt aggregates, group breakdowns and ranking ties while leaving engine status OK and verification SUPPORTED. The independent evaluator rejects those corrupted outputs.
- The new matrix ran before and after the safety fixes. Raw reports are preserved separately.
- Legacy benchmark smoke completed. Its semantic macro-F1 output must not be confused with numerical correctness; the new numeric check can fail even when semantic typing succeeds.
- git diff --check passed.

## Reproduce

From the repository checkout:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe experiments/accuracy.py
.\.venv\Scripts\python.exe experiments/run_all.py --mode smoke --seed 42
```

The independent runner writes timestamped JSON under outputs/experiments/independent_accuracy by default. Use --output to select another directory. It makes no model-provider or database calls. Ordinary-phrasing failures are intentionally reported without crashing the runner; inspect summary.failed to use the result as a release gate.

## Limits and research integrity

- The reference calculation is independently implemented; the cases were designed by the same developer improving the system. This is not independent authorship, a blinded held-out trial or external validation.
- The safety fixtures were used for debugging; their post-fix success is regression evidence, not an unbiased estimate of failure prevalence.
- Main tables use generic business columns and synthetic values. Results do not establish performance across real enterprise domains. No inferential confidence intervals are claimed because templates share datasets and some fixtures repeat.
- Numerical checks concern structured outputs, not arbitrary narrative text, statistical validity or causation.
- New currency guards recognize explicitly named Currency, Currency Code and ISO Currency columns. They do not infer all unit conventions, verify ISO code membership, convert currencies or infer undocumented row grain.
- The new safety guards apply to the analyst question path. Dashboard KPIs, forecasting, AutoML, anomaly methods and other analytics endpoints have not been independently validated by this matrix.
- Browser regression tests demonstrate scripted workflows with synthetic data. A real-user usability study has not been performed.
- No competing product/model comparison or publication-ready superiority claim was made.

## Deliverables

- phase-6-summary.md: this report.
- phase-6-before/accuracy-*.json and phase-6-after/accuracy-*.json: full raw runs.
- phase-6-failures.csv: all remaining failing cases.
- phase-6-results.csv: before/after family counts and coverage.
- phases-1-to-6-changes.patch: cumulative local implementation.
