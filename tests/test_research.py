import pandas as pd
from aura import AuraOrchestrator, EvidenceClaim, EvidenceVerifier
from benchmark.generate import FAMILIES, generate_family
from benchmark.perturbations import LEVELS, perturb
from experiments.metrics import classification_metrics, grounding_metrics

def test_all_benchmark_families_are_reproducible_and_typed():
    assert len(FAMILIES) == 8
    for family in FAMILIES:
        first, second = generate_family(family, 42, 24), generate_family(family, 42, 24)
        assert first.frame.equals(second.frame)
        assert set(first.ground_truth.semantic_roles).issubset(first.frame.columns)
        assert first.ground_truth.anomaly_rows == [23]

def test_perturbations_preserve_ground_truth_column_mapping():
    example = generate_family("retail", 42, 24)
    for level in LEVELS:
        result = perturb(example, level, 123)
        assert set(result.dataset.ground_truth.semantic_roles).issubset(result.dataset.frame.columns)
        assert set(result.column_mapping) == set(example.ground_truth.semantic_roles)

def test_verifier_accepts_grounded_claim_and_rejects_wrong_number():
    evidence = {"evidence_id":"e1","dataset_id":"d1","source_columns":["Revenue"],"filters":{},"method":"pandas sum","result":{"sum":100.0}}
    good = EvidenceClaim.numeric(claim_text="Revenue is 100", evidence=evidence, value=100.0, operation="sum")
    bad = EvidenceClaim.numeric(claim_text="Revenue is 999", evidence=evidence, value=999.0, operation="sum")
    verifier = EvidenceVerifier()
    assert verifier.verify([good], [evidence]).status == "SUPPORTED"
    assert verifier.verify([bad], [evidence]).status == "UNSUPPORTED"

def test_verified_answer_has_bounded_repair_and_no_llm_requirement():
    frame = pd.DataFrame({"Order ID":range(16),"Order Date":pd.date_range("2025-01-01",periods=16),"Revenue":range(100,116),"Region":["North","South"]*8})
    result = AuraOrchestrator().answer("What is revenue by region?", frame, "test")
    assert result["status"] == "OK"
    assert result["verification"]["status"] == "SUPPORTED"
    assert 0 <= result["repair_attempts"] <= 2

def test_metrics_are_calculated_not_hard_coded():
    metrics = classification_metrics({"a":"revenue","b":"region"},{"a":"revenue","b":"category"})
    assert metrics["accuracy"] == .5
    assert grounding_metrics([{ "claim_type":"numerical", "verification_status":"SUPPORTED" }])["supported_claim_rate"] == 1.0
