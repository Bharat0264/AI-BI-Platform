# Evidence-Verified Visualization Engine (EVVE)

EVVE is an additive backend component. Existing Flask routes, Plotly dashboard charts and legacy Matplotlib helpers are unchanged. A chart is built only after deterministic computation creates compact `AnalyticsEvidence`; the chart verifier reads that evidence rather than a raw uploaded dataset.

## Contract

`VisualizationSpecification` contains chart type, dataset/version identifiers, metric definition, dimensions, aggregation, filters, temporal scope, unit/currency, axes, series, evidence IDs and verification status. `VisualizationVerifier` returns one of `VERIFIED`, `INVALID`, `AMBIGUOUS`, `INSUFFICIENT_EVIDENCE`, or `UNSUPPORTED`.

The deterministic recommendation function supports bar/column, line, scatter, histogram, box, heatmap, treemap, Sankey only when a valid flow contract is supplied, and forecast only when explicit finite lower/upper intervals are supplied. The initial series builder supplies aggregate bar/histogram-compatible data; other chart types remain contract-gated until their specific evidence builders are implemented.

## APIs

```python
from aura import EvidenceVerifiedVisualizationEngine

engine = EvidenceVerifiedVisualizationEngine()
result = engine.build(
    frame, dataset_id="dataset", dataset_version_id="source-hash",
    metric_column="Sales", dimension="Region", aggregation="sum",
)
```

`compute_visualization_evidence`, `build_visualization_specification`, `VisualizationVerifier`, and `independent_series_oracle` are also public APIs. The oracle uses Decimal/Python grouping rather than pandas aggregation.

For SIIE results, `conditional_from_impact` emits separately named conditional specifications. It returns `AMBIGUOUS` and never chooses Gross or Net Sales from numerical appearance.

## Verification

EVVE validates evidence/dataset-version identity, metric and aggregation definitions, filters and scope, currency/unit equality, exact ordered series values, finite values, category alignment, supported axes/scales, and chart-specific prerequisites. It rejects stale evidence, manipulated values, misleading log axes, and Sankey or forecast requests without the required evidence.

## Reproduction

```sh
python -m pytest tests/test_evve.py -q
python -m experiments.evve_contracts
```

The experiment is a deterministic valid-versus-invalid contract demonstration. It reports individual verification outcomes and does not claim an accuracy metric or benchmark score.
