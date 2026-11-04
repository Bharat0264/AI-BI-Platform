# Evidence lifecycle analysis

## Root cause and correction

An ambiguous `sales` question executes two candidate computations. SIIE additionally executes two broader impact diagnostics (aggregate/group/rank/chart) for the same candidates. All four records were persisted as conditional evidence and `report_evidence` counted every non-current record, producing 4 exclusions where the legacy report-candidate contract expected 2.

The records were not duplicate IDs and no conditional record was selected. The defect was classification: report candidate selection treated impact diagnostics as candidate conclusions. The correction adds immutable roles:

- `CONDITIONAL_CANDIDATE`: a selectable-after-clarification computation; it is `UNRESOLVED`, report-ineligible as a conclusion, and counted when report candidate selection excludes it.
- `INTERPRETATION_IMPACT_DIAGNOSTIC`: separately computed comparison lineage; it is persisted for inspection, `UNRESOLVED`, and omitted from report candidate selection/counts.
- `RESOLVED` evidence (default role): may be selected only when current and scope/definition dependencies remain valid.

Lifecycle state is independent from role: a record can be `CURRENT`, `STALE`, `UNKNOWN`, `UNRESOLVED`, or rejected by verifier. Conditional evidence is never `CURRENT`; stale/unknown dependencies remain visible with reasons. The report selector accepts only current, report-eligible resolved evidence. Persistence remains insert-once by evidence ID; it does not overwrite source history.

The regression asserts two conditional candidates are excluded, two impact diagnostics are preserved, and diagnostics cannot inflate exclusion accounting. This is a documented filtering correction, not a weaker expectation.
