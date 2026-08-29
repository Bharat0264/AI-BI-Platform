import pandas as pd
from aura import AuraOrchestrator

def frame():
    return pd.DataFrame({"Order ID": range(16), "Order Date": pd.date_range("2025-01-01", periods=16), "Revenue": range(100, 116), "Profit": range(10, 26), "Region": ["North", "South"] * 8, "Customer": [f"C{i%4}" for i in range(16)]})

def test_semantics_profile_and_kpis():
    result = AuraOrchestrator().inspect(frame())
    roles = {x["column"]: x["semantic_role"] for x in result["semantic_schema"]}
    assert roles["Revenue"] == "revenue"
    assert result["profile"]["rows"] == 16
    assert any(k["name"] == "Revenue" for k in result["kpis"])

def test_verified_answer_and_insufficient_data():
    aura = AuraOrchestrator()
    answer = aura.answer("What is revenue by region?", frame())
    assert answer["status"] == "OK" and answer["evidence"][0]["result"]["sum"] == 1720.0
    lowest = aura.answer("Which region has the lowest revenue?", frame())
    assert lowest["evidence"][0]["result"]["requested_result"] == {"direction": "lowest", "dimension": "North", "value": 856.0}
    assert "North has the lowest Revenue" in lowest["answer"]
    assert aura.answer("What is employee morale?", frame())["status"] == "INSUFFICIENT DATA"

def test_ml_task_inference():
    assert AuraOrchestrator().ml.infer_task(frame(), "Revenue") == "regression"

def test_analysis_rejects_non_numeric_measure():
    try:
        AuraOrchestrator().run_analysis("Revenue by region", frame(), measure="Region", dimension="Region")
    except ValueError as error:
        assert "does not contain numeric values" in str(error)
        return
    assert False, "Expected a non-numeric measure to be rejected"

def test_root_cause_decline_is_evidence_grounded():
    df = pd.DataFrame({"Order ID": range(12), "Order Date": pd.date_range("2025-01-01", periods=12, freq="MS"), "Revenue": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 50], "Region": ["North"] * 11 + ["South"]})
    aura = AuraOrchestrator(); evidence, answer = aura.anomalies.root_cause(df, aura.schema.infer(df))
    assert evidence.result["premise_verified"] is True
    assert evidence.uncertainty["causal_claim"] is False

def test_automl_rejects_missing_target():
    try:
        AuraOrchestrator().ml.train(frame(), "missing")
    except ValueError:
        return
    assert False, "Expected validation error"
