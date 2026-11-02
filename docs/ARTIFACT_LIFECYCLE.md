# Phase 4: Dependency freshness and reviewed recomputation

Implemented locally; no commit, push or deployment performed. Backend/API functionality; existing screen unchanged.

## Result
Evidence -> saved answers -> reports now have explicit dependency records. Freshness is calculated on read against the recorded dataset snapshot, latest referenced definition version and relevant semantic corrections. Old answer text, values, evidence and exported files are preserved. A definition change or disable action is detected even for an answer inserted after that change using an older in-flight calculation.

Read-time evaluation is deliberate: no bulk update can miss a late insert or partially mark a graph. There is no background notification process or stored authoritative stale flag. Clients must read lifecycle metadata to see current freshness. This is not a serializable multi-document transaction: a definition changing after a check can make an artifact stale on its next read.

## States
- CURRENT: recorded dependencies match the checked context. This is freshness, not certification of accuracy or business meaning.
- STALE: a referenced definition changed/was disabled, a relevant source correction changed, an ancestor is stale, or the user is viewing a different active dataset snapshot.
- UNRESOLVED: no selected supported answer/interpretation exists.
- UNKNOWN: legacy tracking metadata is missing, a dependency is missing/foreign, or a malformed/cyclic/over-depth graph cannot be safely resolved.

Reasons are included, with source artifact IDs and nested dependency reasons. Semantic-correction checks compare only source columns used by the evidence. Changing unrelated definitions or corrections leaves unaffected answers current. Exact-column and per-request selections do not depend on an unrelated saved default.

A snapshot mismatch means stale for the current active context; it does not claim the historical calculation was wrong for its original immutable snapshot. Older artifacts without lifecycle metadata remain UNKNOWN rather than being retroactively certified.

## API: read artifacts
- POST /api/ask now returns query_id and lifecycle along with the answer, evidence and verification.
- GET /api/aura/answers returns the newest 100 workspace answers and their current lifecycle. GET /api/aura/answers/<query_id> reads one, including the original response and replay information.
- GET /api/aura/reports and GET /api/aura/reports/<report_id> provide the corresponding report metadata and dependency state.
- Lists include historical snapshots in the current workspace; state is evaluated relative to the active dataset. Direct reads are workspace-scoped. Foreign IDs return 404.
- Load a dataset first. The existing application workspace context is used; this adds no authentication system.

## API: recompute an answer
1. POST /api/aura/answers/<query_id>/recompute with {}. This computes and returns a preview, review_token, saved:false and original answer ID. It does not insert a new answer or evidence.
2. Review the preview. POST the same route with:
```json
{"confirmed":true,"review_token":"TOKEN_FROM_PREVIEW"}
```
3. The server recalculates the result and compares its deterministic fingerprint to the reviewed preview. Missing or changed fingerprints return 409. Unresolved or unverified previews cannot be saved.
4. Successful confirmation stores new evidence and a new answer with recomputed_from referencing the original ID. The original answer/evidence remain unchanged. A lineage link is not a freshness dependency: the new result does not inherit the old answer's staleness.

The fingerprint includes the requested plan, dataset ID, selected definition/version, relevant evidence contents and corrections; random evidence IDs and timestamps are excluded. It is a change-detection token, not authentication.

Replay retains explicit per-request/exact-column choices. A question that originally relied on a saved default uses the latest applicable default when replayed. Load the original dataset snapshot; changed data returns 409 rather than silently applying the old question to different data. Legacy answers without a replay request return 409 and require a new question. The server does not retain every raw snapshot automatically, so a user may need to reload the original source.

## Reports
Every PDF export now has a UUID filename instead of overwriting AI_Business_Report.pdf. The browser download name remains familiar, while the server retains separate files.

The evidence register selects up to 10 current evidence records from the exact workspace/dataset. It excludes stale, unresolved and untracked records encountered during selection and states this in the report. Conditional interpretations are not treated as selected business answers. Each evidence entry retains its own scope, which can differ from filtered dashboard metrics; the report explicitly notes that distinction. Freshness does not independently validate the dashboard forecast or report calculations.

GET /api/report creates a new export and returns X-AURA-Report-ID and X-AURA-Freshness headers. To regenerate an existing report, first recompute any desired stale answers, then use:

GET /api/report?recomputed_from=<report_id>

This preserves the original dataset and recorded region/category filters, creates a new file and registry record, and records the predecessor. New filter arguments are rejected during regeneration; changed snapshots and legacy unknown filter recipes require a fresh report. Old PDFs and registry entries remain untouched. The current evidence register is rebuilt; excluded stale answers are not silently rewritten or copied as current.

Repository-level reports can also depend on answer IDs or existing parent-report IDs, with same-workspace/snapshot checks. This supports transitive freshness through composed reports. Missing or cyclic references are conservatively UNKNOWN. Traversal is bounded to 64 dependency levels. No report composer screen is introduced.

## Validation
- Full suite: 101 passed in 3.28 seconds, including 18 Phase 4 regression cases.
- Benchmark smoke: completed, one computed record, zero skipped; execution check only.
- git diff --check: passed.
- Coverage: direct/transitive invalidation, immutable old values, unrelated explicit answers, late inserts, disabled definitions, source corrections, workspace/snapshot boundaries, legacy/missing/cyclic references, scoped evidence selection, unresolved interpretation exclusion, preview without persistence, changed-preview rejection, reviewed replay lineage, invalid replay contexts, report regeneration/filter preservation, and unique export filenames.
- Database/provider behavior is mocked. Report route tests use temporary placeholder bytes; filename tests mock PDF construction. No new PDF layout is introduced, and this phase does not claim visual PDF QA or production concurrency/load validation.

## Implementation boundaries and next work
Artifact freshness depends on the dependencies actually recorded. Legacy or externally modified artifacts may be incomplete. Large histories/graphs have not been load-tested. Existing legacy history endpoints and the current frontend do not automatically display these new API lifecycle fields. Connect definition confirmation, conditional selection, freshness badges and reviewed recomputation to the existing UI next, then perform end-to-end user-flow validation.
