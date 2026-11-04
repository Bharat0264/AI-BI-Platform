# Developer AI Analyst testing workflow

This workflow is for local regression and manual API testing only. It is not an independent benchmark, human study, or publication result. It never reads files under an external benchmark package or hidden labels.

## API contract

`POST /api/ask` accepts `{ "question": string, "definition"?: {"measure_column": string}, "scope"?: object, "expected_dataset_id"?: string, "expected_workspace_id"?: string }`. A successful deterministic response includes `status`, `answer`, `plan`, `evidence`, `claims`, `verification`, `query_id`, lifecycle state, and citations. Ambiguous requests add `alternatives`, `clarification`, `interpretation_check`, `semantic_interpretation_impact`, and `conditional_visualizations`.

`EvidenceVerifier` validates an evidence ID/dataset ID, source columns, filters, result path, operation binding, finite expected value, and tolerance. It rejects duplicate evidence IDs and mismatched values. LLM narration is optional compact-evidence commentary only and is returned as `NOT_VERIFIED`; it cannot replace deterministic answer text.

## Run

```sh
/private/tmp/aura-py312-venv/bin/python -m experiments.developer_analyst_smoke
/private/tmp/aura-py312-venv/bin/python -m pytest tests/test_answer_correctness.py tests/test_interpretations.py tests/test_semantic_impact.py tests/test_evve.py tests/test_dashboard_consistency.py tests/test_lifecycle.py -q
```

The smoke script uses in-memory sample frames. It verifies total/ranking arithmetic, unsupported-causal refusal, ambiguity with conditional SIIE/EVVE output, a verified chart contract, and a verified dashboard component. Its output is expressly developer-only.

## Coverage and integration boundary

- Core/API correctness: `test_answer_correctness`, `test_questions`, `test_scopes`, `test_definitions`, API/auth/security tests.
- SIIE: `test_interpretations`, `test_semantic_impact`; impacts are integrated in ambiguous `AuraOrchestrator.answer` responses.
- EVVE: `test_evve`; conditional specs are added to ambiguous response payloads but do not replace legacy Flask/Plotly charts.
- Dashboard consistency: `test_dashboard_consistency`; currently a reusable backend module, not an `/api/ask` or dashboard-publication route. Consumers must invoke it before export/publication.

## Known supported boundary

The question grammar supports deterministic single-table totals, averages, simple grouping and highest/lowest rankings. It refuses unsupported dates/filters without supported scope, ratios/margins, forecasts, causal explanations, multi-measure questions, ambiguous dimensions, mixed currencies, invalid/non-finite measures, and missing group labels. SIIE comparison is bounded to 32 candidates. Evidence binding verifies computed-record integrity, not the real-world truth of a business definition.
