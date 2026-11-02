"""Dependency freshness and reviewed immutable recomputation regression tests."""
import importlib
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import mongomock
import pandas as pd
import pytest

from aura import AuraOrchestrator
from persistence.mongo import _set_test_client, ensure_indexes
from persistence.repositories import AuraRepository


def frame():
    return pd.DataFrame({"Gross Sales": [100, 200, 300, 400], "Net Sales": [90, 150, 250, 300],
                         "Region": ["North", "South", "North", "South"]})


@pytest.fixture
def scoped():
    client = mongomock.MongoClient()
    _set_test_client(client, "lifecycle_test")
    ensure_indexes()
    store = AuraRepository(client.lifecycle_test)
    workspace = store.workspace("Main")
    dataset = store.dataset(workspace, "sales.csv", frame(), "data/sales.csv")
    store.save_definition(workspace, dataset, "sales", "Net Sales", "revenue", 0, "Analyst")
    return store, workspace, dataset


def answer(scoped, question="What is sales?", definition=None):
    store, workspace, dataset = scoped
    result = AuraOrchestrator().answer(question, frame(), dataset, definition=definition,
        saved_definitions=store.definition_defaults(workspace, dataset))
    for evidence in result["evidence"]:
        store.evidence(workspace, dataset, evidence)
    query_id = store.query(workspace, dataset, question, result, request_definition=definition)
    return query_id, result


def update(scoped):
    store, workspace, dataset = scoped
    return store.save_definition(workspace, dataset, "sales", "Gross Sales", "revenue", 1, "Analyst")


def test_stale_dependency_propagates_without_mutating_history(scoped):
    store, workspace, dataset = scoped
    qid, result = answer(scoped)
    eid = result["evidence"][0]["evidence_id"]
    direct = store.report(workspace, dataset, [eid], "outputs/first.pdf")
    via_answer = store.report(workspace, dataset, [], "outputs/second.pdf", answer_ids=[qid])
    parent = store.report(workspace, dataset, [], "outputs/parent.pdf", parent_report_ids=[via_answer])
    original_answer = deepcopy(store._artifact(workspace, "answer", qid))
    original_evidence = deepcopy(store._artifact(workspace, "evidence", eid))
    assert store.artifact_state(workspace, "report", parent)["status"] == "CURRENT"
    update(scoped)
    for kind, key in [("evidence", eid), ("answer", qid), ("report", direct), ("report", via_answer), ("report", parent)]:
        assert store.artifact_state(workspace, kind, key)["status"] == "STALE"
    assert store._artifact(workspace, "answer", qid) == original_answer
    assert store._artifact(workspace, "evidence", eid) == original_evidence


def test_exact_and_explicit_answers_are_not_invalidated_by_unrelated_defaults(scoped):
    store, workspace, dataset = scoped
    exact, _ = answer(scoped, "What is gross sales?")
    explicit, _ = answer(scoped, definition={"measure_column": "Net Sales"})
    report = store.report(workspace, dataset, [], "outputs/report.pdf", answer_ids=[exact, explicit])
    update(scoped)
    assert store.artifact_state(workspace, "answer", exact)["status"] == "CURRENT"
    assert store.artifact_state(workspace, "answer", explicit)["status"] == "CURRENT"
    assert store.artifact_state(workspace, "report", report)["status"] == "CURRENT"


def test_disabled_defaults_and_late_answer_inserts_are_detected(scoped):
    store, workspace, dataset = scoped
    old = AuraOrchestrator().answer("What is sales?", frame(), dataset,
        saved_definitions=store.definition_defaults(workspace, dataset))
    store.save_definition(workspace, dataset, "sales", None, None, 1, "Analyst", active=False)
    for evidence in old["evidence"]:
        store.evidence(workspace, dataset, evidence)
    late = store.query(workspace, dataset, "What is sales?", old)
    assert store.artifact_state(workspace, "answer", late)["status"] == "STALE"


def test_semantic_correction_changes_invalidate_only_relevant_sources(scoped):
    store, workspace, dataset = scoped
    qid, _ = answer(scoped, "What is net sales?")
    store.save_inspection(dataset, AuraOrchestrator().inspect(frame(), dataset))
    store.correct_semantics(dataset, {"Gross Sales": "cost"})
    assert store.artifact_state(workspace, "answer", qid)["status"] == "CURRENT"
    store.correct_semantics(dataset, {"Net Sales": "cost"})
    assert store.artifact_state(workspace, "answer", qid)["status"] == "STALE"


def test_workspace_and_changed_snapshot_boundaries(scoped):
    store, workspace, dataset = scoped
    qid, result = answer(scoped)
    other = store.workspace("Other")
    with pytest.raises(ValueError):
        store.artifact_detail(other, "answer", qid)
    with pytest.raises(ValueError):
        store.report(other, dataset, [], "outputs/foreign.pdf")
    changed = frame()
    changed.loc[0, "Net Sales"] = 900
    newer = store.dataset(workspace, "sales.csv", changed, "data/sales.csv")
    assert store.artifact_state(workspace, "answer", qid, newer)["status"] == "STALE"
    assert store.artifact_state(workspace, "answer", qid, dataset)["status"] == "CURRENT"
    with pytest.raises(ValueError):
        store.report(workspace, newer, [result["evidence"][0]["evidence_id"]], "outputs/mixed.pdf")


def test_legacy_missing_and_cyclic_dependencies_are_not_current(scoped):
    store, workspace, dataset = scoped
    legacy = {"query_id": "legacy", "workspace_id": workspace, "dataset_id": dataset,
              "answerability": "OK", "evidence_ids": [], "created_at": "2020"}
    store.db.ai_queries.insert_one(legacy)
    assert store.artifact_state(workspace, "answer", "legacy")["status"] == "UNKNOWN"
    bad = store.report(workspace, dataset, [], "outputs/bad.pdf")
    store.db.reports.update_one({"report_id": bad}, {"$set": {"parent_report_ids": [bad]}})
    assert store.artifact_state(workspace, "report", bad)["status"] == "UNKNOWN"
    store.db.reports.update_one({"report_id": bad}, {"$set": {"parent_report_ids": ["missing"]}})
    assert store.artifact_state(workspace, "report", bad)["status"] == "UNKNOWN"


def test_report_evidence_selection_excludes_stale_foreign_and_other_snapshots(scoped):
    store, workspace, dataset = scoped
    _, stale = answer(scoped)
    update(scoped)
    _, fresh = answer(scoped)
    other = store.workspace("Other")
    other_dataset = store.dataset(other, "sales.csv", frame(), "data/sales.csv")
    foreign = AuraOrchestrator().answer("What is net sales?", frame(), other_dataset)
    store.evidence(other, other_dataset, foreign["evidence"][0])
    selected, excluded = store.report_evidence(workspace, dataset)
    assert [item["evidence_id"] for item in selected] == [fresh["evidence"][0]["evidence_id"]]
    assert excluded == 1


@pytest.fixture
def api(scoped, monkeypatch):
    store, workspace, dataset = scoped
    server = importlib.import_module("server")
    current = {"frame": frame(), "workspace": workspace}
    def context(data, source):
        return current["workspace"], store.dataset(current["workspace"], source, data, "data/sales.csv")
    monkeypatch.setattr(server, "dataset_from_request", lambda: (current["frame"].copy(), "sales.csv"))
    monkeypatch.setattr(server, "aura_context", context)
    monkeypatch.setattr(server, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(server, "PERSISTENCE", store)
    monkeypatch.setattr(server, "add_record", Mock())
    monkeypatch.setattr(server.GeminiEvidenceProvider, "explain", Mock(return_value=None))
    return server.app.test_client(), current, server


def test_api_reviewed_recompute_preserves_original_and_has_new_lineage(scoped, api):
    store, workspace, dataset = scoped
    client, _, _ = api
    old = client.post("/api/ask", json={"question": "What is sales?"}).get_json()
    assert old["lifecycle"]["status"] == "CURRENT"
    qid = old["query_id"]
    original = store._artifact(workspace, "answer", qid)
    update(scoped)
    assert client.get(f"/api/aura/answers/{qid}").get_json()["lifecycle"]["status"] == "STALE"
    preview = client.post(f"/api/aura/answers/{qid}/recompute", json={}).get_json()
    assert preview["saved"] is False
    assert preview["preview"]["claims"][0]["computed_value"] == 1000
    assert store.db.ai_queries.count_documents({}) == 1
    assert client.post(f"/api/aura/answers/{qid}/recompute", json={"confirmed": True}).status_code == 409
    saved = client.post(f"/api/aura/answers/{qid}/recompute", json={"confirmed": True, "review_token": preview["review_token"]}).get_json()
    assert saved["saved"] is True
    assert saved["query_id"] != qid
    assert saved["recomputed_from"] == qid
    assert saved["lifecycle"]["status"] == "CURRENT"
    assert store._artifact(workspace, "answer", qid) == original
    assert len(client.get("/api/aura/answers").get_json()["items"]) == 2


def test_api_preview_becomes_invalid_after_another_definition_change(scoped, api):
    store, workspace, dataset = scoped
    client, _, _ = api
    old, _ = answer(scoped)
    preview = client.post(f"/api/aura/answers/{old}/recompute", json={}).get_json()
    update(scoped)
    assert client.post(f"/api/aura/answers/{old}/recompute", json={"confirmed": True, "review_token": preview["review_token"]}).status_code == 409
    assert store.db.ai_queries.count_documents({}) == 1


def test_api_recompute_rejects_foreign_legacy_and_changed_snapshot(scoped, api):
    store, workspace, dataset = scoped
    client, current, _ = api
    qid, _ = answer(scoped)
    current["workspace"] = store.workspace("Other")
    assert client.get(f"/api/aura/answers/{qid}").status_code == 404
    assert client.post(f"/api/aura/answers/{qid}/recompute", json={}).status_code == 404
    current["workspace"] = workspace
    current["frame"].loc[0, "Net Sales"] = 900
    assert client.post(f"/api/aura/answers/{qid}/recompute", json={}).status_code == 409
    current["frame"] = frame()
    store.db.ai_queries.update_one({"query_id": qid}, {"$unset": {"request_definition": ""}})
    assert client.post(f"/api/aura/answers/{qid}/recompute", json={}).status_code == 409


def test_api_recompute_does_not_save_unresolved_results(scoped, api):
    store, workspace, dataset = scoped
    client, _, _ = api
    qid, _ = answer(scoped)
    store.save_definition(workspace, dataset, "sales", None, None, 1, "Analyst", active=False)
    preview = client.post(f"/api/aura/answers/{qid}/recompute", json={}).get_json()
    assert preview["preview"]["status"] == "CLARIFICATION_REQUIRED"
    assert client.post(f"/api/aura/answers/{qid}/recompute", json={"confirmed": True, "review_token": preview["review_token"]}).status_code == 400
    assert store.db.ai_queries.count_documents({}) == 1


def test_regenerated_report_is_new_artifact_not_dependency_on_stale_predecessor(scoped):
    store, workspace, dataset = scoped
    _, old = answer(scoped)
    rid = store.report(workspace, dataset, [old["evidence"][0]["evidence_id"]], "outputs/old.pdf")
    original = store._artifact(workspace, "report", rid)
    update(scoped)
    _, current = answer(scoped)
    new = store.report(workspace, dataset, [current["evidence"][0]["evidence_id"]], "outputs/new.pdf", recomputed_from=rid)
    assert store.artifact_state(workspace, "report", rid)["status"] == "STALE"
    assert store.artifact_state(workspace, "report", new)["status"] == "CURRENT"
    assert store._artifact(workspace, "report", rid) == original
    assert store._artifact(workspace, "report", new)["recomputed_from"] == rid


def test_report_route_uses_scoped_evidence_and_preserves_filter_recipe(scoped, api, monkeypatch, tmp_path):
    store, workspace, dataset = scoped
    client, _, server = api
    answer(scoped)
    monkeypatch.setattr(server, "financial_dashboard_available", lambda df: True)
    monkeypatch.setattr(server, "prepare_dataset", lambda df: df)
    filters_seen = []
    def filter_rows(df, payload=None):
        filters_seen.append(payload)
        return df, [], [], ["North"], ["Office"]
    monkeypatch.setattr(server, "filter_dataset", filter_rows)
    monkeypatch.setattr(server, "predict_sales", lambda df: (None, pd.DataFrame()))
    monkeypatch.setattr(server, "kpis", lambda df: [])
    monkeypatch.setattr(server, "executive_summary", lambda df: [])
    monkeypatch.setattr(server, "recommendations", lambda df: [])
    monkeypatch.setattr(server, "anomalies", lambda df: [])
    seen = []
    def generate(*args, **kwargs):
        seen.append(kwargs["evidence"])
        target = tmp_path / f"report-{len(seen)}.pdf"
        target.write_bytes(b"%PDF-1.4\nmock")
        return str(target)
    monkeypatch.setattr(server, "generate_pdf_report", generate)
    first = client.get("/api/report")
    assert first.status_code == 200
    rid = first.headers["X-AURA-Report-ID"]
    original = store._artifact(workspace, "report", rid)
    update(scoped)
    answer(scoped)
    second = client.get(f"/api/report?recomputed_from={rid}")
    assert second.status_code == 200
    assert second.headers["X-AURA-Report-ID"] != rid
    assert filters_seen[-1] == {"regions": ["North"], "categories": ["Office"]}
    assert store._artifact(workspace, "report", rid) == original
    assert seen[0][0]["definition"]["saved_reference"]["version"] == 1
    assert seen[1][0]["definition"]["saved_reference"]["version"] == 2
    assert len(seen[1]) == 1
    assert client.get(f"/api/report?recomputed_from={rid}&region=South").status_code == 400
    assert len(client.get("/api/aura/reports").get_json()["items"]) == 2
    assert client.get(f"/api/aura/reports/{rid}").get_json()["lifecycle"]["status"] == "STALE"


def test_pdf_generator_never_reuses_the_export_filename(monkeypatch, tmp_path):
    generator = importlib.import_module("report_generator")
    monkeypatch.setattr(generator, "__file__", str(tmp_path / "app" / "report_generator.py"))
    monkeypatch.setattr(generator, "SimpleDocTemplate", Mock())
    first = generator.generate_pdf_report("First")
    second = generator.generate_pdf_report("Second")
    assert first != second
    assert Path(first).parent == tmp_path / "outputs" / "reports"

def test_unselected_interpretations_are_never_reported_as_current_selected_evidence(scoped):
    store, workspace, dataset = scoped
    store.save_definition(workspace, dataset, "sales", None, None, 1, "Analyst", active=False)
    qid, response = answer(scoped)
    assert response["status"] == "CLARIFICATION_REQUIRED"
    assert store.artifact_state(workspace, "answer", qid)["status"] == "UNRESOLVED"
    for evidence in response["evidence"]:
        assert store.artifact_state(workspace, "evidence", evidence["evidence_id"])["status"] == "UNRESOLVED"
    selected, excluded = store.report_evidence(workspace, dataset)
    assert selected == [] and excluded == 2


@pytest.mark.parametrize("body", [[], "question", None])
def test_ask_rejects_non_object_json(api, body):
    client, _, _ = api
    assert client.post("/api/ask", json=body).status_code == 400
