"""Regression tests for bounded, conditional business-definition comparisons."""
import importlib
from unittest.mock import Mock

import mongomock
import pandas as pd
import pytest

from aura import AuraOrchestrator, EvidenceVerifier
from persistence.mongo import _set_test_client
from persistence.repositories import AuraRepository


def sales_frame():
    return pd.DataFrame({"Gross Sales": [100, 200, 300, 400],
                         "Net Sales": [90, 150, 250, 300],
                         "Region": ["North", "South", "North", "South"]})


def test_differing_definitions_have_individually_verified_evidence():
    df = sales_frame()
    original = df.copy(deep=True)
    result = AuraOrchestrator().answer("What is sales?", df, "dataset")
    assert result["status"] == "CLARIFICATION_REQUIRED"
    assert result["interpretation_check"]["impact"] == "DIFFERENT_TESTED_OUTPUTS"
    assert result["interpretation_check"]["coverage"] == "COMPLETE"
    assert result["plan"]["analytical_task"] == "interpretation comparison"
    assert [item["comparison"]["value"] for item in result["alternatives"]] == [1000, 790]
    for claim in result["claims"]:
        assert EvidenceVerifier().verify([claim], result["evidence"]).status == "SUPPORTED"
    assert "Gross Sales" in result["answer"] and "Net Sales" in result["answer"]
    assert all(item["definition"]["filters"] == {} for item in result["alternatives"])
    pd.testing.assert_frame_equal(original, df)


def test_equal_totals_do_not_imply_same_definition_or_same_breakdown():
    df = sales_frame()
    df["Net Sales"] = [200, 100, 400, 300]
    aura = AuraOrchestrator()
    total = aura.answer("What is sales?", df)
    assert total["interpretation_check"]["impact"] == "SAME_TESTED_OUTPUT"
    assert total["status"] == "CLARIFICATION_REQUIRED"
    assert total["clarification"]["field"] == "measure_column"
    grouped = aura.answer("What is sales by region?", df)
    assert grouped["interpretation_check"]["impact"] == "DIFFERENT_TESTED_OUTPUTS"
    ranking = aura.answer("Which region has the highest sales?", df)
    assert ranking["interpretation_check"]["impact"] == "DIFFERENT_TESTED_OUTPUTS"
    assert ranking["alternatives"][0]["comparison"]["winners"] == ["South"]
    assert ranking["alternatives"][1]["comparison"]["winners"] == ["North"]


def test_explicit_selection_and_exact_column_questions():
    aura = AuraOrchestrator()
    result = aura.answer("What is average sales?", sales_frame(), definition={"measure_column": "Net Sales"})
    assert result["status"] == "OK"
    assert result["claims"][0]["computed_value"] == 197.5
    assert result["definition"]["selection"] == "explicit"
    assert result["definition"]["aggregation"] == "mean"
    assert result["claims"][0]["verification_status"] == "SUPPORTED"
    exact = aura.answer("What is net sales?", sales_frame())
    assert exact["status"] == "OK"
    assert exact["definition"]["measure_column"] == "Net Sales"
    # Selection cannot override an explicitly requested other column.
    assert aura.answer("What is net sales?", sales_frame(), definition={"measure_column": "Gross Sales"})["status"] == "INSUFFICIENT DATA"


@pytest.mark.parametrize("definition", [{}, [], "Net Sales", {"measure_column": 1},
    {"measure_column": "Net Sales", "filters": {}}, {"measure_column": "Region"},
    {"measure_column": "missing"}])
def test_invalid_definition_is_rejected(definition):
    assert AuraOrchestrator().answer("What is sales?", sales_frame(), definition=definition)["status"] == "INSUFFICIENT DATA"


def test_corrections_constrain_candidates_and_failed_candidate_is_not_hidden():
    aura = AuraOrchestrator()
    corrected = aura.answer("What is sales?", sales_frame(), corrections={"Gross Sales": "cost"})
    assert corrected["status"] == "OK"
    assert corrected["definition"]["measure_column"] == "Net Sales"
    df = sales_frame()
    df["Net Sales"] = None
    result = aura.answer("What is sales?", df)
    assert result["status"] == "CLARIFICATION_REQUIRED"
    assert result["interpretation_check"]["coverage"] == "PARTIAL"
    assert result["interpretation_check"]["impact"] == "UNDETERMINED"
    assert result["alternatives"][1]["status"] == "INSUFFICIENT DATA"


def test_execution_budget_never_reports_complete_coverage():
    df = pd.DataFrame({f"Sales {index}": [index, index + 1] for index in range(33)})
    corrections = {col: "revenue" for col in df}
    result = AuraOrchestrator().answer("What is sales?", df, corrections=corrections)
    check = result["interpretation_check"]
    assert check["candidate_count"] == 33
    assert check["executed_count"] == 32
    assert check["coverage"] == "PARTIAL"
    assert check["impact"] == "UNDETERMINED"
    # Untested choices can still be selected and computed explicitly.
    assert AuraOrchestrator().answer("What is sales?", df, corrections=corrections,
                                    definition={"measure_column": "Sales 32"})["status"] == "OK"


def test_unverified_execution_cannot_establish_stability():
    result = AuraOrchestrator({"verifier": False}).answer("What is sales?", sales_frame())
    assert result["interpretation_check"]["impact"] == "UNDETERMINED"
    assert all(item["status"] == "UNVERIFIED" for item in result["alternatives"])


def test_persisted_definition_bindings_and_conditional_history():
    client = mongomock.MongoClient()
    db = client.phase2_test
    store = AuraRepository(db)
    df = sales_frame()
    workspace = store.workspace("Phase 2")
    dataset = store.dataset(workspace, "sales.csv", df, "data/sales.csv")
    result = AuraOrchestrator().answer("What is sales?", df, dataset)
    for item in result["evidence"]:
        store.evidence(workspace, dataset, item)
        saved = db.analytics_evidence.find_one({"evidence_id": item["evidence_id"]})
        assert saved["definition"] == item["definition"]
        assert saved["result_bindings"] == item["result_bindings"]
        assert EvidenceVerifier().verify([c for c in result["claims"] if c["evidence_id"] == item["evidence_id"]], [saved]).status == "SUPPORTED"
    store.query(workspace, dataset, "What is sales?", result)
    saved = db.ai_queries.find_one({"dataset_id": dataset})
    assert saved["clarification"] == result["clarification"]
    assert saved["interpretation_check"] == result["interpretation_check"]


def test_api_returns_conditional_results_and_accepts_explicit_definition(monkeypatch):
    _set_test_client(mongomock.MongoClient(), "phase2_api_test")
    server = importlib.import_module("server")
    monkeypatch.setattr(server, "dataset_from_request", lambda: (sales_frame(), "sales.csv"))
    monkeypatch.setattr(server, "aura_context", lambda *args: ("workspace", "dataset"))
    monkeypatch.setattr(server, "get_setting", lambda key, default=None: default)
    store = Mock()
    store.corrections.return_value = {}
    monkeypatch.setattr(server, "PERSISTENCE", store)
    monkeypatch.setattr(server, "add_record", Mock())
    provider = Mock(return_value=None)
    monkeypatch.setattr(server.GeminiEvidenceProvider, "explain", provider)
    api = server.app.test_client()
    result = api.post("/api/ask", json={"question": "What is sales?"}).get_json()
    assert result["status"] == "CLARIFICATION_REQUIRED"
    assert len(result["alternatives"]) == 2
    provider.assert_not_called()
    selected = api.post("/api/ask", json={"question": "What is sales?",
                                        "definition": {"measure_column": "Net Sales"}}).get_json()
    assert selected["status"] == "OK"
    assert selected["definition"]["measure_column"] == "Net Sales"
    assert selected["claims"][0]["computed_value"] == 790
    assert provider.call_count == 1


def test_all_invalid_alternatives_return_insufficient_data():
    df = sales_frame()
    df["Gross Sales"] = None
    df["Net Sales"] = None
    result = AuraOrchestrator().answer("What is sales?", df)
    assert result["status"] == "INSUFFICIENT DATA"
    assert result["evidence"] == []
    assert len(result["alternatives"]) == 2
