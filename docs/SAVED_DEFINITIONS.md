# Phase 3: Confirmed, versioned business definitions

Implemented locally. No commit, push or deployment performed.

## What works
A user can explicitly confirm that `sales` means `Net Sales` for the current workspace and exact dataset snapshot. Future supported questions using `sales` use that column automatically and disclose the saved version. Every confirmation or disable action appends a new immutable version. Evidence and query history retain the definition ID, version and scope that an answer used.

Precedence: an exact column named in the question wins; an admissible per-request column choice wins over a saved default; otherwise a matching saved term default is used. A saved default invalidated by semantic corrections produces INSUFFICIENT DATA and asks for review rather than silently falling back. Existing unsupported question forms remain unsupported.

Defaults are term-specific. Saving `sales` does not also redefine `revenue`. They are column mappings, not new formulas or policies for returns, taxes, currency, filters or periods.

## API workflow
Use the active dataset and existing current-workspace context. These routes do not accept a caller-supplied workspace or dataset override.

1. GET `/api/aura/definitions` returns active defaults with their versions and current scope IDs.
2. PUT `/api/aura/definitions` with the following JSON explicitly confirms a first definition:
```json
{"term":"sales","measure_column":"Net Sales","expected_version":0,"confirmed":true}
```
The column must pass the current deterministic calculation and evidence verification for this term. An exact column already matching the term cannot be overridden by a saved default.
3. POST `/api/ask` with `{"question":"What is sales?"}` reuses the saved choice. The answer says which version was used. The response definition and evidence include a saved_reference.
4. GET `/api/aura/definitions?term=sales` returns all versions, including disabled versions, oldest first.
5. PUT the new column with the latest expected_version to revise the definition. A stale version returns HTTP 409 and requires the caller to reload and review.
6. DELETE `/api/aura/definitions` with `{"term":"sales","expected_version":2,"confirmed":true}` appends a disabled version. It does not erase history. Questions return to interpretation comparison when multiple candidates remain.
7. Reconfirm after disabling using the latest history version, not version zero.

Allowed terms: sales, revenue, profit, cost, costs, quantity. confirmed must be the boolean true; expected_version must be a non-negative integer. Malformed or unconfirmed writes return 400. Missing datasets return 400. Concurrent inserts are protected by a unique workspace/dataset/term/version index and return 409 on conflict.

## Snapshot isolation and compatibility
The old dataset key used filename, row count and column names, which could conflate different data. New registrations hash the actual values, column names, dtypes, index, row order and filename. Full float precision is preserved. Serialization is chunked at 4,096 rows to bound temporary allocations; the application only serializes, never unpickles external input for this hash.

Changing data creates a new snapshot identity and requires new confirmation. Identical snapshots in different workspaces have separate defaults. Existing legacy dataset records remain untouched but are not treated as the same snapshot or allowed to donate defaults automatically. Re-uploading identical data can reuse its current identity under the same runtime; serializer/runtime changes can cause a conservative identity miss. No automatic dataset-family inference or cross-file transfer is implemented.

The application has to read the data to compute its identity. Large-dataset hashing latency has not been benchmarked here.

## Storage and concurrency
business_definitions is append-only. Each version includes a stable definition_id, term, selected column, semantic role, active flag, version, workspace/dataset IDs, confirmation timestamp and confirmation actor label. A read-then-insert protocol plus the unique compound index prevents two writers from claiming the same next version; no multi-document transaction is needed for this append-only operation.

This uses the application's existing current-workspace context and user-name label. It does not introduce authentication or prove the identity of the confirming person.

Evidence and answer history preserve the exact referenced version. This phase does not mark old reports stale or recompute them; dependency tracking is the next phase.

## Validation
- Full suite: 83 passed in 2.82 seconds, including 21 new Phase 3 regression cases.
- Benchmark smoke: completed with one computed record, zero skipped. Execution check only, not an accuracy or novelty certification.
- git diff --check: passed.
- Tests cover append-only history, stale/concurrent version conflicts, disable/reconfirm, invalid confirmations, malformed versions, workspace and snapshot boundaries, single-float-step data changes, legacy record isolation, explicit-column precedence, per-request overrides without persistence, semantic-correction invalidation, evidence/history references, repository reopening and the REST lifecycle.
- Test data is synthetic and the database/provider infrastructure is mocked. Production MongoDB concurrency and large-data performance have not been exercised.

## Interface boundary
This is a ready-to-use backend/API implementation. The existing Flask/vanilla-JavaScript interface remains unchanged. Confirmation controls can be added in the later interface phase. A plain question or a one-request definition selection never saves a default implicitly.

## Next phase
Track answer/report dependencies on definition versions and data snapshots, mark affected artifacts stale when a definition changes, and support reviewed recomputation while preserving prior answers.
