import pandas as pd
import mongomock
from aura import AuraOrchestrator
from persistence.mongo import ensure_indexes, _set_test_client
from persistence.repositories import AuraRepository

def repo():
    client=mongomock.MongoClient(); _set_test_client(client,"aura_test"); ensure_indexes()
    return AuraRepository(client.aura_test), client.aura_test

def test_workspace_dataset_schema_and_immutable_evidence():
    store,db=repo(); df=pd.DataFrame({"Order Date":["2025-01-01"]*12,"Revenue":range(12),"Region":["N"]*12})
    workspace=store.workspace("Test Workspace"); dataset=store.dataset(workspace,"test.csv",df,"data/test.pkl")
    inspection=AuraOrchestrator().inspect(df,"test.csv"); store.save_inspection(dataset,inspection); store.correct_semantics(dataset,{"Region":"region"})
    assert store.corrections(dataset)=={"Region":"region"}
    evidence=AuraOrchestrator().answer("What is revenue by region?",df,"test.csv")["evidence"][0]; store.evidence(workspace,dataset,evidence); store.evidence(workspace,dataset,evidence)
    assert db.analytics_evidence.count_documents({"evidence_id":evidence["evidence_id"]}) == 1
    assert db.datasets.find_one({"dataset_id":dataset})["workspace_id"] == workspace

def test_run_history_ai_insufficient_and_report_persist_across_repository_instances():
    store,db=repo(); df=pd.DataFrame({"Order Date":pd.date_range("2024-01-01",periods=20,freq="MS").astype(str),"Revenue":[100]*19+[50],"Target":range(20),"Region":["North"]*19+["South"]})
    workspace=store.workspace(); dataset=store.dataset(workspace,"test.csv",df,"data/test.pkl"); aura=AuraOrchestrator()
    run=aura.run_analysis("descriptive statistics",df,"test.csv",measure="Revenue"); store.analytics(workspace,dataset,"descriptive statistics",run)
    ml=aura.ml.train(df,"Target"); store.ml(workspace,dataset,"Target",ml)
    answer=aura.answer("employee morale",df,"test.csv"); store.query(workspace,dataset,"employee morale",answer); store.report(workspace,dataset,[run["evidence"]["evidence_id"]],"outputs/report.pdf")
    evidence,_=aura.anomalies.root_cause(df,aura.schema.infer(df),"test.csv"); store.investigation(workspace,dataset,evidence.__dict__)
    reopened=AuraRepository(db)
    assert db.analytics_runs.count_documents({"dataset_id":dataset}) == 1
    assert db.ml_runs.count_documents({"dataset_id":dataset}) == 1
    assert db.ai_queries.find_one({"dataset_id":dataset})["answerability"] == "INSUFFICIENT DATA"
    assert db.reports.count_documents({"dataset_id":dataset}) == 1
    assert db.anomaly_investigations.count_documents({"dataset_id":dataset}) == 1
    assert reopened.corrections(dataset) == {}

def test_expected_indexes_exist():
    _,db=repo()
    assert "workspace_id_1" in db.workspaces.index_information()
    assert "evidence_id_1" in db.analytics_evidence.index_information()
