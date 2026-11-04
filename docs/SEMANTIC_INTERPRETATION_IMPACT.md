# Semantic Interpretation Impact Engine (SIIE)

SIIE extends AURA-BI's existing conditional interpretation comparison. It does not choose a business definition. Given already-admissible candidate columns, it deterministically computes each candidate's sum, mean, confirmed region/category group series, descending ranking, highest/lowest groups and bar-chart-ready series. Every candidate calculation is an `AnalyticsEvidence` record with exact `sum` and `mean` claim bindings verified by the existing `EvidenceVerifier`.

## Public API

```python
from aura import EvidenceVerifier, analyze_semantic_interpretation_impact

report = analyze_semantic_interpretation_impact(
    frame, dataset_id="example", business_term="sales", semantic_role="revenue",
    candidates=["Gross Sales", "Net Sales"], dimensions=["Region", "Category"],
    verifier=EvidenceVerifier(),
)
```

The result is JSON-serializable and includes per-candidate evidence IDs and verification, pairwise absolute/relative differences, grouped/ranking/chart comparisons, a Semantic Impact Graph, coverage, and explicit unsupported-condition codes. Inputs are never mutated.

For equal total Gross Sales and Net Sales that distribute value differently by region, the result includes the following shape:

```json
{
  "classification": ["RANKING_SENSITIVE", "VISUALIZATION_SENSITIVE"],
  "pairs": [{
    "aggregate": {"equal_within_tolerance": true},
    "grouped_values_differ": true,
    "ranking_reversal": true,
    "chart_shape_changed": true,
    "output_equivalence": "RANKING_DIFFERENT"
  }]
}
```

## Classifications

- `STABLE_TESTED_OUTPUT`: all executed, supported candidate outputs are equal for the tested aggregate, grouping, ranking and available chart shapes.
- `VALUE_SENSITIVE`: at least one candidate pair has a different tested aggregate.
- `RANKING_SENSITIVE`: at least one confirmed grouping has a different ranking or highest/lowest result.
- `VISUALIZATION_SENSITIVE`: at least one available normalized chart series differs.
- `INCOMPLETE_COMPARISON`: a candidate was bounded out, failed verification, or a requested grouping/chart comparison was unavailable.

Classifications describe only tested numerical consequences. They never establish semantic equivalence, causal effects, or a preferred business definition.

## Boundaries

SIIE accepts only candidate columns already admitted by the semantic interpretation path. It excludes individual missing/invalid/non-finite measure values under the existing evidence policy and records their count; it refuses candidates with no finite values, mixed currencies, ambiguous units, or unsafe grouping labels. It records missing group labels as an unsupported condition and marks coverage partial. It does not infer formulas, conversions, joins, new business policies, or unbounded alternatives.

In ambiguous `/api/ask` responses, the report is returned under `semantic_interpretation_impact`; no frontend change is required. The Semantic Impact Graph has `BusinessTerm -> CandidateDefinition -> AnalyticalPlan -> Evidence -> KPI/Chart/Result` nodes and edges for audit/export use.
