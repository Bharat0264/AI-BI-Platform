"""Confirmed, versioned defaults: scope, precedence, persistence and REST lifecycle."""
import importlib
from copy import deepcopy
from unittest.mock import Mock

import mongomock
import pandas as pd
import pytest
from pymongo.errors import DuplicateKeyError

from aura import AuraOrchestrator
from persistence.definitions import DefinitionConflict
from persistence.mongo import _set_test_client, ensure_indexes
from persistence.repositories import AuraRepository


def frame():
    return pd.DataFrame({"Gross Sales": [100, 200, 300, 400], "Net Sales": [90, 150, 250, 300],
                         "Region": ["North", "South", "North", "South"]})


@pytest.fixture
def store():
    client = mongomock.MongoClient()
    _set_test_client(client, "definition_test")
    ensure_indexes()
    return AuraRepository(client.definition_test)


def scope(store, name="Main", data=None):
    workspace = store.workspace(name)
    data = frame() if data is None else data
    dataset = store.dataset(workspace, "sales.csv", data, "data/sales.csv")
    return workspace, dataset


def save(store, workspace, dataset, column="Net Sales", version=0):
    return store.save_definition(workspace, dataset, "sales", column, "revenue", version, "Analyst")


def test_append_only_versions_disable_and_reconfirm(store):
    workspace, dataset = scope(store)
    first = save(store, workspace, dataset)
    original = deepcopy(first)
    second = save(store, workspace, dataset, "Gross Sales", 1)
    assert first["definition_id"] == second["definition_id"]
    assert second["version"] == 2
    assert store.definition_defaults(workspace, dataset)["sales"] == second
    assert store.definition_history(workspace, dataset, "sales")[0] == original
    with pytest.raises(DefinitionConflict):
        save(store, workspace, dataset, version=1)
    disabled = store.save_definition(workspace, dataset, "sales", None, None, 2, "Analyst", active=False)
    assert disabled["version"] == 3
    assert not store.definition_defaults(workspace, dataset)
    again = save(store, workspace, dataset, version=3)
    assert again["version"] == 4
    assert again["definition_id"] == first["definition_id"]
    assert len(store.definition_history(workspace, dataset, "sales")) == 4


@pytest.mark.parametrize("expected", [-1, True, "0", None, 1.5])
def test_invalid_expected_versions(store, expected):
    workspace, dataset = scope(store)
    with pytest.raises(ValueError):
        save(store, workspace, dataset, version=expected)
    assert not store.definition_history(workspace, dataset, "sales")


def test_workspace_snapshot_and_term_isolation(store):
    workspace, dataset = scope(store)
    save(store, workspace, dataset)
    other_workspace, other_dataset = scope(store, "Other")
    assert other_dataset != dataset
    assert not store.definition_defaults(other_workspace, other_dataset)
    with pytest.raises(ValueError, match="does not belong"):
        store.definition_defaults(other_workspace, dataset)
    with pytest.raises(ValueError):
        store.definition_history(other_workspace, dataset, "sales")
    with pytest.raises(ValueError):
        save(store, other_workspace, dataset)
    assert store.definition_history(workspace, dataset, "revenue") == []
    changed = frame()
    changed.loc[0, "Net Sales"] = 900
    _, changed_id = scope(store, data=changed)
    assert changed_id != dataset
    assert not store.definition_defaults(workspace, changed_id)
    _, repeat_id = scope(store, data=frame().copy(deep=True))
    assert repeat_id == dataset
    renamed = store.dataset(workspace, "other.csv", frame(), "data/other.csv")
    assert renamed != dataset


def test_saved_reference_is_recorded_and_exact_requests_win(store):
    workspace, dataset = scope(store)
    saved = save(store, workspace, dataset)
    defaults = store.definition_defaults(workspace, dataset)
    aura = AuraOrchestrator()
    response = aura.answer("What is sales?", frame(), dataset, saved_definitions=defaults)
    assert response["status"] == "OK"
    assert response["claims"][0]["computed_value"] == 790
    assert response["definition"]["selection"] == "saved definition"
    reference = response["definition"]["saved_reference"]
    assert reference["definition_id"] == saved["definition_id"] and reference["version"] == 1
    assert "saved definition sales, version 1: Net Sales" in response["answer"]
    exact = aura.answer("What is gross sales?", frame(), dataset, saved_definitions=defaults)
    assert exact["claims"][0]["computed_value"] == 1000
    assert "saved_reference" not in exact["definition"]
    explicit = aura.answer("What is sales?", frame(), dataset, definition={"measure_column": "Gross Sales"}, saved_definitions=defaults)
    assert explicit["claims"][0]["computed_value"] == 1000
    assert store.definition_defaults(workspace, dataset) == defaults
    store.evidence(workspace, dataset, response["evidence"][0])
    store.query(workspace, dataset, "What is sales?", response)
    assert store.db.analytics_evidence.find_one({"dataset_id": dataset})["definition"]["saved_reference"] == reference
    assert store.db.ai_queries.find_one({"dataset_id": dataset})["definition"]["saved_reference"] == reference


def test_corrections_invalidate_default_and_wrong_snapshot_cannot_reuse(store):
    workspace, dataset = scope(store)
    save(store, workspace, dataset)
    defaults = store.definition_defaults(workspace, dataset)
    aura = AuraOrchestrator()
    result = aura.answer("What is sales?", frame(), dataset,
                         corrections={"Net Sales": "cost"}, saved_definitions=defaults)
    assert result["status"] == "INSUFFICIENT DATA"
    assert "no longer admissible" in result["answer"]
    assert aura.answer("What is sales?", frame(), "different", saved_definitions=defaults)["status"] == "INSUFFICIENT DATA"


def test_concurrent_version_collision_is_not_overwritten(store, monkeypatch):
    workspace, dataset = scope(store)
    save(store, workspace, dataset)
    def collision(*args, **kwargs):
        raise DuplicateKeyError("another writer won")
    monkeypatch.setattr(store.db.business_definitions, "insert_one", collision)
    with pytest.raises(DefinitionConflict, match="concurrent"):
        save(store, workspace, dataset, version=1)
    assert len(store.definition_history(workspace, dataset, "sales")) == 1


@pytest.fixture
def api(store, monkeypatch):
    server = importlib.import_module("server")
    current = {"frame": frame(), "workspace": "Main"}
    def context(data, source):
        workspace = store.workspace(current["workspace"])
        return workspace, store.dataset(workspace, source, data, "data/sales.csv")
    monkeypatch.setattr(server, "dataset_from_request", lambda: (current["frame"].copy(deep=True), "sales.csv"))
    monkeypatch.setattr(server, "aura_context", context)
    monkeypatch.setattr(server, "get_setting", lambda key, default=None: {"name": "Analyst"} if key == "current_user" else default)
    monkeypatch.setattr(server, "PERSISTENCE", store)
    monkeypatch.setattr(server, "add_record", Mock())
    monkeypatch.setattr(server.GeminiEvidenceProvider, "explain", Mock(return_value=None))
    return server.app.test_client(), current


def request(column="Net Sales", version=0):
    return {"term": "sales", "measure_column": column, "expected_version": version, "confirmed": True}


def test_api_confirmation_reuse_history_conflicts_and_disable(api):
    client, current = api
    assert client.get("/api/aura/definitions").get_json()["definitions"] == {}
    first = client.put("/api/aura/definitions", json=request())
    assert first.status_code == 200
    assert first.get_json()["definition"]["confirmed_by"] == "Analyst"
    result = client.post("/api/ask", json={"question": "What is sales?"}).get_json()
    assert result["status"] == "OK" and result["definition"]["saved_reference"]["version"] == 1
    assert result["claims"][0]["computed_value"] == 790
    assert client.put("/api/aura/definitions", json=request("Gross Sales", 0)).status_code == 409
    assert client.put("/api/aura/definitions", json=request("Gross Sales", 1)).status_code == 200
    history = client.get("/api/aura/definitions?term=sales").get_json()["history"]
    assert [item["version"] for item in history] == [1, 2]
    assert history[0]["measure_column"] == "Net Sales"
    assert client.post("/api/ask", json={"question": "What is sales?"}).get_json()["claims"][0]["computed_value"] == 1000
    assert client.delete("/api/aura/definitions", json={"term": "sales", "expected_version": 2, "confirmed": True}).status_code == 200
    assert client.post("/api/ask", json={"question": "What is sales?"}).get_json()["status"] == "CLARIFICATION_REQUIRED"
    assert client.put("/api/aura/definitions", json=request(version=3)).get_json()["definition"]["version"] == 4
    current["workspace"] = "Other"
    assert client.get("/api/aura/definitions").get_json()["definitions"] == {}
    assert client.get("/api/aura/definitions?term=sales").get_json()["history"] == []
    current["workspace"] = "Main"
    current["frame"].loc[0, "Net Sales"] = 900
    assert client.get("/api/aura/definitions").get_json()["definitions"] == {}


@pytest.mark.parametrize("body", [
    {"term": "sales", "measure_column": "Net Sales", "expected_version": 0},
    {"term": "sales", "measure_column": "Net Sales", "expected_version": 0, "confirmed": "true"},
    {"term": "sales", "measure_column": "Region", "expected_version": 0, "confirmed": True},
    {"term": "sales", "measure_column": "missing", "expected_version": 0, "confirmed": True},
    {"term": "sales", "measure_column": "Net Sales", "expected_version": True, "confirmed": True},
    {"term": "sales", "measure_column": "Net Sales", "expected_version": 0, "confirmed": True, "workspace_id": "other"},
    {"term": "unknown", "measure_column": "Net Sales", "expected_version": 0, "confirmed": True},
    [],
])
def test_api_invalid_confirmation_never_saves(api, body):
    client, _ = api
    assert client.put("/api/aura/definitions", json=body).status_code == 400
    assert client.get("/api/aura/definitions").get_json()["definitions"] == {}


def test_api_cannot_save_default_that_overrides_exact_column(api):
    client, current = api
    current["frame"] = frame().rename(columns={"Gross Sales": "Sales"})
    assert client.put("/api/aura/definitions", json=request()).status_code == 400

def test_snapshot_identity_preserves_precision_schema_and_old_registrations(store):
    from hashlib import sha256
    import numpy as np
    workspace, dataset = scope(store)
    # Pre-v2 registrations are preserved but cannot donate defaults to new snapshots.
    data = frame()
    legacy_digest = sha256(f"sales.csv|{len(data)}|{list(data.columns)}".encode()).hexdigest()
    store.db.datasets.insert_one({"workspace_id": workspace, "dataset_id": "legacy",
                                  "content_hash": legacy_digest})
    save(store, workspace, "legacy")
    assert store.definition_defaults(workspace, dataset) == {}
    tiny_change = data.copy(deep=True).astype({"Net Sales": "float64"})
    first = store.dataset(workspace, "sales.csv", tiny_change, "data/sales.csv")
    tiny_change.loc[0, "Net Sales"] = np.nextafter(90., 91.)
    second = store.dataset(workspace, "sales.csv", tiny_change, "data/sales.csv")
    assert first != second and first != dataset
    assert store.db.datasets.find_one({"dataset_id": "legacy"}) is not None
    assert AuraRepository(store.db).definition_defaults(workspace, "legacy")["sales"]["version"] == 1
