"""Explicit filter/window execution, independent arithmetic and immutable replay."""
from copy import deepcopy
from datetime import datetime
import importlib
from unittest.mock import Mock

import mongomock
import pandas as pd
import pytest

from aura import AuraOrchestrator, EvidenceVerifier
from experiments.oracle import aggregate
from persistence.mongo import _set_test_client, ensure_indexes
from persistence.repositories import AuraRepository


def frame():
    return pd.DataFrame({"Order Date": ["2025-01-01", "2025-01-31T23:59:59", "2025-02-01", "2025-02-28", "2025-03-01"],
                         "Revenue": [10., 20., 30., 60., 900.], "Region": ["North"] * 4 + ["South"],
                         "Category": ["Office", "Tools", "Office", "Tools", "Office"]})


def scope(compare=True):
    result = {"filters": {"Region": ["North"]}, "date_column": "Order Date",
              "period": {"start": "2025-02-01", "end": "2025-02-28"}}
    if compare:
        result["compare_to"] = {"start": "2025-01-01", "end": "2025-01-31"}
    return result


def test_filters_dates_and_comparison_match_independent_reference():
    df = frame(); original = df.copy(deep=True)
    result = AuraOrchestrator().answer("What is revenue?", df, scope=scope())
    assert result["status"] == "OK"
    current = aggregate([30., 60.], "sum"); baseline = aggregate([10., 20.], "sum")
    assert result["comparison"]["current"] == current
    assert result["comparison"]["baseline"] == baseline
    assert result["comparison"]["difference"] == current - baseline
    assert result["comparison"]["percent_change"] == (current - baseline) / baseline * 100
    assert result["comparison"]["period_lengths"] == {"current": 28, "baseline": 31}
    assert len(result["evidence"]) == 3
    assert result["evidence"][0]["scope"]["selected_rows"] == 2
    assert result["evidence"][1]["scope"]["selected_rows"] == 2
    assert result["evidence"][0]["filters"]["date"]["end_exclusive"] == "2025-03-01"
    assert result["verification"]["status"] == "SUPPORTED"
    assert "no filters applied" not in result["answer"]
    pd.testing.assert_frame_equal(df, original)


def test_mean_comparison_and_single_period_breakdowns():
    result = AuraOrchestrator().answer("What is average revenue?", frame(), scope=scope())
    assert result["comparison"]["current"] == 45
    assert result["comparison"]["baseline"] == 15
    grouped = AuraOrchestrator().answer("Show revenue by category", frame(), scope=scope(False))
    assert grouped["status"] == "OK"
    assert grouped["evidence"][0]["result"]["ranking"] == {"Tools": 60., "Office": 30.}


@pytest.mark.parametrize("baseline,status", [(0., "UNDEFINED_ZERO_BASELINE"), (-10., "NOT_REPORTED_NEGATIVE_BASELINE")])
def test_nonpositive_baseline_never_reports_a_misleading_percentage(baseline, status):
    df = frame(); df.loc[0:1, "Revenue"] = baseline
    result = AuraOrchestrator().answer("What is revenue?", df, scope=scope())
    assert result["status"] == "OK"
    assert result["comparison"]["percent_change"] is None
    assert result["comparison"]["percent_change_status"] == status
    assert not any(claim["operation"] == "percent_change" for claim in result["claims"])


@pytest.mark.parametrize("invalid", [
    [], {"unknown": True}, {"filters": {"Missing": ["North"]}}, {"filters": {"Region": []}},
    {"filters": {"Region": ["north"]}}, {"filters": {"Region": "North"}},
    {"date_column": "Order Date"}, {"period": {"start": "2025-02-01", "end": "2025-02-28"}},
    {"date_column": "Order Date", "period": {"start": "2025-02-30", "end": "2025-03-01"}},
    {"date_column": "Order Date", "period": {"start": "2025-03-01", "end": "2025-02-01"}},
    {"date_column": "Order Date", "compare_to": {"start": "2025-01-01", "end": "2025-01-31"}},
    {"date_column": "Order Date", "period": {"start": "2025-04-01", "end": "2025-04-30"}},
    {"date_column": "Order Date", "period": {"start": "2025-02-01", "end": "2025-02-28"}, "compare_to": {"start": "2025-02-10", "end": "2025-03-01"}},
])
def test_invalid_scopes_never_fall_back_to_global_totals(invalid):
    result = AuraOrchestrator().answer("What is revenue?", frame(), scope=invalid)
    assert result["status"] == "INSUFFICIENT DATA"
    assert result["evidence"] == []


@pytest.mark.parametrize("bad", [None, "01/02/2025", "2025-02-30", "2025-01-01T00:00:00Z", "2025-01-01T00:00:00+05:30"])
def test_invalid_or_zoned_source_dates_require_correction(bad):
    df = frame(); df.loc[0, "Order Date"] = bad
    result = AuraOrchestrator().answer("What is revenue?", df, scope=scope())
    assert result["status"] == "INSUFFICIENT DATA"


def test_unselected_invalid_dates_do_not_contaminate_explicit_filter_scope():
    df = frame(); df.loc[4, "Order Date"] = "invalid"
    assert AuraOrchestrator().answer("What is revenue?", df, scope=scope())["status"] == "OK"


def test_multiple_date_columns_require_explicit_choice_and_roles_are_authoritative():
    df = frame(); df["Ship Date"] = ["2025-03-01"] * len(df)
    assert AuraOrchestrator().answer("What is revenue?", df, scope=scope())["status"] == "OK"
    assert AuraOrchestrator().answer("What is revenue?", df, scope=scope(), corrections={"Order Date": "identifier"})["status"] == "INSUFFICIENT DATA"


def test_currency_conversion_is_not_implied_by_period_comparison():
    df = frame(); df["Currency"] = ["EUR", "EUR", "USD", "USD", "USD"]
    assert AuraOrchestrator().answer("What is revenue?", df, scope=scope())["status"] == "INSUFFICIENT DATA"
    assert AuraOrchestrator().answer("What is revenue?", df, scope=scope(False))["status"] == "OK"


def test_scoped_ambiguity_requires_measure_selection_before_baseline_comparison():
    df = frame().rename(columns={"Revenue": "Gross Sales"}); df["Net Sales"] = df["Gross Sales"] / 2
    ambiguous = AuraOrchestrator().answer("What is sales?", df, scope=scope())
    assert ambiguous["status"] == "CLARIFICATION_REQUIRED"
    assert "only the current period" in ambiguous["answer"]
    assert ambiguous["alternatives"][1]["comparison"]["value"] == 45
    resolved = AuraOrchestrator().answer("What is sales?", df, scope=scope(), definition={"measure_column": "Net Sales"})
    assert resolved["comparison"]["current"] == 45
    assert resolved["comparison"]["baseline"] == 15


def test_scoped_source_positions_do_not_depend_on_dataframe_index_labels():
    df = frame(); df.index = [1, 1, 2, 2, 3]
    normal = AuraOrchestrator().answer("What is revenue?", frame(), scope=scope(False))
    duplicate = AuraOrchestrator().answer("What is revenue?", df, scope=scope(False))
    assert duplicate["status"] == "OK"
    assert duplicate["evidence"][0]["scope"]["row_position_sha256"] == normal["evidence"][0]["scope"]["row_position_sha256"]


def test_comparison_claims_cannot_borrow_another_field_or_scope():
    result = AuraOrchestrator().answer("What is revenue?", frame(), scope=scope())
    claim = next(claim for claim in result["claims"] if claim["operation"] == "difference")
    assert EvidenceVerifier().verify([claim], result["evidence"]).status == "SUPPORTED"
    wrong = deepcopy(claim); wrong["result_path"] = ["current"]
    assert EvidenceVerifier().verify([wrong], result["evidence"]).status == "UNSUPPORTED"
    wrong = deepcopy(claim); wrong["filters"] = {}
    assert EvidenceVerifier().verify([wrong], result["evidence"]).status == "UNSUPPORTED"


def test_grouped_period_comparison_is_rejected_as_unsupported():
    result = AuraOrchestrator().answer("What is revenue by category?", frame(), scope=scope())
    assert result["status"] == "INSUFFICIENT DATA"


def test_api_replay_keeps_scope_and_comparison_evidence_dependencies(monkeypatch):
    client = mongomock.MongoClient(); _set_test_client(client, "scope_test"); ensure_indexes()
    store = AuraRepository(client.scope_test); server = importlib.import_module("server")
    df = frame().rename(columns={"Revenue": "Gross Sales"}); df["Net Sales"] = df["Gross Sales"] / 2
    workspace = store.workspace("Scope test"); dataset = store.dataset(workspace, "sales.csv", df, "data/sales.csv")
    store.save_definition(workspace, dataset, "sales", "Net Sales", "revenue", 0, "Analyst")
    monkeypatch.setattr(server, "PERSISTENCE", store)
    monkeypatch.setattr(server, "dataset_from_request", lambda: (df.copy(), "sales.csv"))
    monkeypatch.setattr(server, "aura_context", lambda *args: (workspace, dataset))
    monkeypatch.setattr(server, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(server, "add_record", Mock())
    monkeypatch.setattr(server.GeminiEvidenceProvider, "explain", lambda *args: None)
    api = server.app.test_client()
    body = {"question": "What is sales?", "scope": scope()}
    old = api.post("/api/ask", json=body).get_json()
    assert old["status"] == "OK"
    qid = old["query_id"]
    assert store._artifact(workspace, "answer", qid)["request_scope"] == scope()
    assert store.artifact_state(workspace, "answer", qid)["status"] == "CURRENT"
    store.save_definition(workspace, dataset, "sales", "Gross Sales", "revenue", 1, "Analyst")
    assert store.artifact_state(workspace, "answer", qid)["status"] == "STALE"
    preview = api.post(f"/api/aura/answers/{qid}/recompute", json={}).get_json()
    assert preview["preview"]["comparison"]["current"] == 90
    assert preview["preview"]["comparison"]["baseline"] == 30
    confirmed = api.post(f"/api/aura/answers/{qid}/recompute", json={"confirmed": True, "review_token": preview["review_token"]}).get_json()
    assert confirmed["saved"] is True
    assert store._artifact(workspace, "answer", confirmed["query_id"])["request_scope"] == scope()
    evidence = confirmed["evidence"][-1]
    store.db.analytics_evidence.delete_one({"evidence_id": evidence["dependency_evidence_ids"][0]})
    assert store.artifact_state(workspace, "evidence", evidence["evidence_id"])["status"] == "UNKNOWN"
    assert api.post("/api/ask", json={**body, "expected_dataset_id": "wrong"}).status_code == 409

def test_independent_scope_oracle_detects_wrong_rows_even_if_totals_match():
    from experiments.scope_checks import generate_scope_cases
    from experiments.accuracy import assess
    case = generate_scope_cases()[0]
    result = AuraOrchestrator().answer(case.question, pd.DataFrame(case.records), scope=case.kwargs["scope"])
    assert assess(case, result) == []
    result["evidence"][0]["scope"]["row_position_sha256"] = "wrong"
    assert "Wrong row selection audit: row_position_sha256" in assess(case, result)


def test_independent_scope_oracle_detects_wrong_date_bounds_and_difference():
    from experiments.scope_checks import generate_scope_cases
    from experiments.accuracy import assess
    case = next(case for case in generate_scope_cases() if "periods" in case.expected)
    result = AuraOrchestrator().answer(case.question, pd.DataFrame(case.records), scope=case.kwargs["scope"])
    assert assess(case, result) == []
    result["evidence"][0]["filters"]["date"]["end_exclusive"] = "2025-02-28"
    result["evidence"][-1]["result"]["difference"] += 1
    errors = assess(case, result)
    assert "Wrong date boundary: end_exclusive" in errors
    assert "Wrong period difference" in errors


def test_minute_precision_iso_source_and_excluded_numeric_rows_are_disclosed():
    df = frame(); df.loc[1, "Order Date"] = "2025-01-31T23:59"; df.loc[3, "Revenue"] = None
    result = AuraOrchestrator().answer("What is revenue?", df, scope=scope())
    assert result["status"] == "OK"
    assert result["comparison"]["current"] == 30
    assert result["comparison"]["baseline"] == 30
    assert result["comparison"]["excluded_numeric_rows"]["current"] == 1
    assert "invalid numeric rows excluded: 1 current" in result["answer"]
