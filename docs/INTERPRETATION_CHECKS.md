# Phase 2: Explicit measure definitions and interpretation checks

Implemented locally; not pushed or deployed.

## User workflow
Ask `What is sales?` when the table has Gross Sales and Net Sales. The answer shows a conditional result for each detected revenue column, asks which should define the measure, and explains whether the tested outputs differ. The existing question box displays this text. Ask `What is net sales?` to select that column explicitly. No new screen or UI dependency was introduced.

The API also supports this request:
```json
{"question":"What is sales?","definition":{"measure_column":"Net Sales"}}
```
A definition is a per-request column selection. It does not create a reusable saved default. Schema-role corrections already saved for the current dataset still constrain the admissible candidates.

## Response contract
- A single resolved measure returns status OK and a definition record naming the column, semantic role, aggregation, grouping, filters, missing-value policy and selection source.
- Ambiguous measures return CLARIFICATION_REQUIRED, alternatives, interpretation_check and clarification options.
- Each successful alternative has independently bound and verified computed evidence. The overall verification status is CONDITIONAL; no interpretation is silently selected.
- SAME_TESTED_OUTPUT means only that the executed requested outputs agree within absolute tolerance 1e-6. It does not establish equivalent meanings or a probability of correctness.
- DIFFERENT_TESTED_OUTPUTS means the requested results differ; grouped questions compare all groups, and highest/lowest questions compare winners and winning values, including ties.
- Comparison is limited to 32 plans. Truncation, failed alternatives or disabled verification result in PARTIAL coverage and UNDETERMINED impact.
- If all detected alternatives fail computation, return INSUFFICIENT DATA with the failed alternatives, rather than suggesting that any of them is verified.

## Evidence and history
Definition records and exact result bindings are preserved in MongoDB evidence. Query history preserves alternatives, clarification details, claims and verification metadata. The question endpoint uses the persistent dataset ID so in-memory and stored evidence identities agree. Evidence is still immutable insert-once.

## Boundaries
This phase compares existing columns detected under the same supported measure role. It does not infer gross-minus-returns formulas, currency conversion, period comparisons, arbitrary filters, metric units, or every possible interpretation. It does not add saved default definitions, versioned contracts, snapshot hashing, dependency invalidation or report recomputation. Existing evidence verification checks consistency with computed evidence, not independent semantic truth. A shared total does not confirm a shared meaning.

Existing specialized analytics endpoints remain separate. The question endpoint explicitly discloses that its calculations cover all supplied rows with no filters applied.

## Validation
- Full suite: 62 tests passed in 2.59 seconds, including 16 Phase 2 regression cases.
- Benchmark smoke: completed with one computed record, zero skipped. This is an execution check, not proof of superiority.
- git diff --check: passed.
- Regression coverage includes unequal and equal totals, different grouped distributions, reversed ranking winners, exact and API-selected columns, invalid selections, authoritative semantic corrections, invalid alternatives, 32-plan truncation, disabled verification, source preservation, and MongoDB evidence/query round trips.
- Tests use synthetic frames and mocked provider/database infrastructure. No production database or model calls are required.

## Next phase
Add explicitly confirmed, workspace-scoped reusable definitions with versions. Their reuse must not silently override an exact column requested in a question. Lifecycle tracking and report invalidation follow after that.
