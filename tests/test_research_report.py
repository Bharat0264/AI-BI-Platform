"""Developer-only opt-in research report security/publication tests."""
import importlib, json, sys
from pathlib import Path
from unittest.mock import Mock
import pandas as pd
import pytest
from aura import AuraOrchestrator, ResearchDashboardPipeline

def frame(): return pd.DataFrame({"Revenue":[100,200],"Region":["N","S"]})

def contract(): return ResearchDashboardPipeline(AuraOrchestrator()).build(df=frame(),dataset_id="d",dataset_version_id="d",questions=["What is revenue by region?"])

def test_manifest_requires_publishable_verified_contract_and_pdf_is_written(tmp_path, monkeypatch):
    result=contract(); manifest=ResearchDashboardPipeline.report_manifest(result)
    assert manifest["publication_decision"]=="PUBLISH_VERIFIED"
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
    generator=importlib.import_module("report_generator")
    # Validate the immutable manifest contract before exercising the endpoint.
    assert manifest["included_components"][0]["visualization_verification"]=="VERIFIED"
    pdf_path, json_path = generator.generate_research_report(result, manifest)
    assert Path(pdf_path).read_bytes().startswith(b"%PDF")
    assert json.loads(Path(json_path).read_text())["report_id"] == manifest["report_id"]
    bad=ResearchDashboardPipeline(AuraOrchestrator()).build(df=frame(),dataset_id="d",dataset_version_id="d",questions=["Why did revenue decline?"])
    with pytest.raises(ValueError): ResearchDashboardPipeline.report_manifest(bad)

def test_research_report_endpoint_blocks_ambiguity_and_bad_requests(monkeypatch):
    import mongomock
    from persistence.mongo import _set_test_client
    _set_test_client(mongomock.MongoClient(),"research_report_api")
    server=importlib.import_module("server")
    store=Mock();store.corrections.return_value={};store.definition_defaults.return_value={}
    monkeypatch.setattr(server,"PERSISTENCE",store)
    monkeypatch.setattr(server,"dataset_from_request",lambda:(pd.DataFrame({"Gross Sales":[1],"Net Sales":[1],"Region":["N"]}),"x.csv"))
    monkeypatch.setattr(server,"aura_context",lambda *_:("w","d"));monkeypatch.setattr(server,"get_setting",lambda *args:{})
    client=server.app.test_client()
    assert client.post("/api/research/report",json={"questions":[]}).status_code==400
    blocked=client.post("/api/research/report",json={"questions":["What is sales?"]})
    assert blocked.status_code==409 and blocked.get_json()["publication_decision"]=="CLARIFICATION_REQUIRED"
    guarded=client.post("/api/research/report",json={"questions":["What is sales?"],"expected_dataset_id":"other"})
    assert guarded.status_code==409
