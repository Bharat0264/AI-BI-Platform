import copy

import numpy as np
import pandas as pd
import pytest

from aura import AuraOrchestrator, EvidenceClaim, EvidenceVerifier


def business_frame():
    return pd.DataFrame({"Revenue": [100, 200, 300, 400], "Profit": [10, 20, 30, 40],
                         "Region": ["North", "South", "North", "South"]})


@pytest.mark.parametrize("question,measure,operation,value", [
    ("What is profit?", "Profit", "sum", 100),
    ("What is revenue?", "Revenue", "sum", 1000),
    ("What is average profit?", "Profit", "mean", 25),
    ("What is average revenue by region?", "Revenue", "mean", 250),
])
def test_requested_measure_and_operation(question, measure, operation, value):
    response = AuraOrchestrator().answer(question, business_frame())
    assert response["status"] == "OK"
    assert response["evidence"][0]["result"]["measure"] == measure
    assert response["claims"][0]["computed_value"] == value
    assert response["claims"][0]["result_path"] == [operation]
    assert response["verification"]["status"] == "SUPPORTED"


@pytest.mark.parametrize("question", [
    "What is profit last month?", "What is revenue in North?", "Predict revenue",
    "What is profit margin?", "What is revenue growth?", "Why did revenue decline?",
    "What is customer count?", "What is revenue and profit?", "What is revenue by channel?",
])
def test_unsupported_requests_never_receive_unfiltered_totals(question):
    assert AuraOrchestrator().answer(question, business_frame())["status"] == "INSUFFICIENT DATA"


def test_missing_measure_and_dimension_do_not_fall_back():
    aura = AuraOrchestrator()
    assert aura.answer("What is profit?", business_frame().drop(columns="Profit"))["status"] == "INSUFFICIENT DATA"
    assert aura.answer("What is revenue by category?", business_frame())["status"] == "INSUFFICIENT DATA"


def test_ambiguity_and_user_corrections():
    df = business_frame().rename(columns={"Revenue": "Gross Sales"})
    df["Net Sales"] = [1, 2, 3, 4]
    aura = AuraOrchestrator()
    assert aura.answer("What is sales?", df)["status"] == "CLARIFICATION_REQUIRED"
    assert aura.answer("What is net sales?", df)["claims"][0]["computed_value"] == 10
    assert aura.answer("What is sales?", df, corrections={"Gross Sales": "cost"})["claims"][0]["computed_value"] == 10
    renamed = business_frame().rename(columns={"Profit": "Result"})
    assert aura.answer("What is profit?", renamed, corrections={"Result": "profit"})["claims"][0]["computed_value"] == 100


def test_numeric_exclusions_and_empty_values():
    aura = AuraOrchestrator()
    for values in ([], [None, None], [np.inf, -np.inf], ["bad", "bad"]):
        assert aura.answer("What is revenue?", pd.DataFrame({"Revenue": values}), corrections={"Revenue": "revenue"})["status"] == "INSUFFICIENT DATA"
    result = aura.answer("What is revenue?", pd.DataFrame({"Revenue": [10, None, np.inf]}))
    assert result["claims"][0]["computed_value"] == 10
    assert result["evidence"][0]["result"]["excluded_rows"] == 2


def test_ranking_ties_and_no_source_mutation():
    df = business_frame()
    df["Profit"] = [10, 10, 10, 10]
    original = df.copy(deep=True)
    response = AuraOrchestrator().answer("Which region has the lowest profit?", df)
    assert response["status"] == "OK"
    assert set(response["evidence"][0]["result"]["requested_result"]["ties"]) == {"North", "South"}
    pd.testing.assert_frame_equal(df, original)


def evidence_fixture():
    return {"evidence_id": "e1", "dataset_id": "d1", "source_columns": ["Profit"],
            "filters": {"year": 2025}, "method": "pandas sum",
            "result": {"sum": 100.0, "mean": 25.0, "rows": 100}}


@pytest.mark.parametrize("change", [
    {"expected_value": 25}, {"result_path": ["rows"]}, {"result_path": ["mean"]},
    {"result_path": None}, {"source_columns": ["Revenue"]}, {"filters": {}},
    {"operation": "su"}, {"expected_value": float("nan")},
    {"expected_value": float("inf")}, {"tolerance": float("inf")},
    {"tolerance": -1}, {"expected_value": True}, {"expected_value": "100"},
])
def test_verifier_rejects_incorrect_bindings(change):
    evidence = evidence_fixture()
    claim = EvidenceClaim.numeric(claim_text="Profit is 100", evidence=evidence, value=100, operation="sum").to_dict()
    claim.update(change)
    assert EvidenceVerifier().verify([claim], [evidence]).status == "UNSUPPORTED"


def test_verifier_recomputes_binding_and_rejects_conflicting_ids():
    evidence = evidence_fixture()
    claim = EvidenceClaim.numeric(claim_text="Profit is 100", evidence=evidence, value=100, operation="sum")
    claim.computed_value = 999
    result = EvidenceVerifier().verify([claim], [evidence])
    assert result.status == "SUPPORTED"
    assert result.claims[0]["computed_value"] == 100
    assert claim.computed_value == 999
    assert EvidenceVerifier().verify([claim], [evidence, copy.deepcopy(evidence)]).status == "UNSUPPORTED"
    assert EvidenceVerifier().verify([], [evidence]).status == "INSUFFICIENT_EVIDENCE"

def test_api_ask_uses_saved_corrections_and_preserves_verified_answer(monkeypatch):
    import importlib
    import mongomock
    from persistence.mongo import _set_test_client

    _set_test_client(mongomock.MongoClient(), "phase1_api_test")
    server = importlib.import_module("server")
    df = business_frame().rename(columns={"Profit": "Result"})
    monkeypatch.setattr(server, "dataset_from_request", lambda: (df, "request.csv"))
    monkeypatch.setattr(server, "aura_context", lambda frame, source: ("workspace", "dataset"))
    monkeypatch.setattr(server, "get_setting", lambda key, default=None: {"Result": "profit"} if key == "aura_schema:request.csv" else default)
    from unittest.mock import Mock
    store = Mock()
    store.corrections.return_value = {"Revenue": "cost"}
    monkeypatch.setattr(server, "PERSISTENCE", store)
    monkeypatch.setattr(server, "add_record", Mock())
    monkeypatch.setattr(server.GeminiEvidenceProvider, "explain", lambda *args: "Invented profit is 999")
    response = server.app.test_client().post("/api/ask", json={"question": "What is profit?"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "OK"
    assert "100.00" in body["answer"] and "999" not in body["answer"]
    assert body["verification"]["status"] == "SUPPORTED"
    assert body["explanation_verification"] == "NOT_VERIFIED"
    assert body["evidence"][0]["dataset_id"] == "dataset"
    store.corrections.assert_called_once_with("dataset")
    unsupported = server.app.test_client().post("/api/ask", json={"question": "What is profit last year?"}).get_json()
    assert unsupported["status"] == "INSUFFICIENT DATA"
    assert unsupported["evidence"] == []
