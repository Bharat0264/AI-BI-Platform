from benchmark.evaluation import decimal_total, development_stress_cases, split_manifest
from experiments.semantic_visual_benchmark import evaluate, metrics

def test_stress_cases_are_explicitly_not_independent_evaluation():
    manifest=split_manifest(); assert manifest["development_stress_case_ids"] and not manifest["independent_evaluation_case_ids"]
    rows=evaluate(development_stress_cases(), ("full",)); assert all(row["split"]=="development_stress" for row in rows)

def test_decimal_oracle_is_standalone_and_metrics_disclose_unmeasured_claims():
    assert decimal_total([{"Revenue":"1.1"},{"Revenue":"2.2"}],"Revenue")==3.3
    summary=metrics(evaluate(development_stress_cases(), ("full",)))
    assert "verified visualization accuracy" in summary["not_measured"][1]
