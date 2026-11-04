# Cross-Dashboard Semantic Consistency and Verification

`DashboardConsistencyEngine` is an additive backend publication gate. It receives declared dashboard components and immutable evidence records; it does not change Flask, frontend, or existing charts.

The dependency graph is `Dataset -> Definition -> Measure -> Aggregation -> Evidence -> Visualization/KPI -> Dashboard Finding`. Each component declares whether it belongs to a `directly_comparable_group`. Only components in the same such group are compared across scope, definition, aggregation, units, and dataset version. This prevents false positives for legitimate filtered, grouped, sampled, or non-additive views.

The engine checks evidence identity and freshness, displayed KPI arithmetic, evidence/component definitions, units/currencies, time scope, filters, dataset versions, and declared cross-view invariants. A result is `PUBLISH_VERIFIED`, `REQUIRE_CLARIFICATION`, or `REJECT`.

- Verified content can publish.
- Conditional/ambiguous content requires clarification.
- Missing, stale, unsupported, invalid, or conflicting content is rejected.

Issues include affected components, invariant, evidence references, severity, explanation, corrective action, and whether a correction such as regenerating a mismatched KPI value is safe. These are descriptive consistency checks, not causal root-cause claims.

Run `python -m pytest tests/test_dashboard_consistency.py -q` and `python -m experiments.dashboard_consistency`. The test dashboard labels are independent expected issue sets and calculate precision, recall, false-positive rate, and coverage; no aggregate research result is asserted.
