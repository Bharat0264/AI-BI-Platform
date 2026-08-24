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
    assert aura.answer("What is employee morale?", frame())["status"] == "INSUFFICIENT DATA"

def test_ml_task_inference():
    assert AuraOrchestrator().ml.infer_task(frame(), "Revenue") == "regression"
