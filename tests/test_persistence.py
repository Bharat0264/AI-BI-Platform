import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from aura import AuraOrchestrator
from persistence.database import Base
import persistence.database as database
from persistence.models import Dataset, Evidence, MLRun, SemanticColumn, AIQuery, Report
from persistence.repositories import AuraRepository

def isolated_repo(tmp_path, monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path / 'aura_test.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    return AuraRepository(), engine

def test_workspace_dataset_semantics_and_evidence_persist(tmp_path, monkeypatch):
    repo,engine=isolated_repo(tmp_path,monkeypatch); df=pd.DataFrame({"Order Date":["2025-01-01"]*12,"Revenue":range(12),"Region":["N"]*12})
    workspace=repo.workspace("Test Workspace"); dataset=repo.dataset(workspace,"test.csv",df,"data/test.pkl")
    inspection=AuraOrchestrator().inspect(df,"test.csv"); repo.save_inspection(dataset,inspection); repo.correct_semantics(dataset,{"Region":"region"})
    evidence=AuraOrchestrator().answer("What is revenue by region?",df,"test.csv")["evidence"][0]; repo.evidence(workspace,dataset,evidence)
    with sessionmaker(bind=engine)() as db:
        assert db.get(Dataset,dataset).workspace_id == workspace
        assert db.get(Evidence,evidence["evidence_id"]).dataset_id == dataset
        assert db.scalar(select(SemanticColumn).where(SemanticColumn.dataset_id==dataset,SemanticColumn.column_name=="Region")).user_corrected_role == "region"

def test_run_query_and_report_records_persist(tmp_path, monkeypatch):
    repo,_=isolated_repo(tmp_path,monkeypatch); df=pd.DataFrame({"Revenue":range(20),"Target":range(20)})
    workspace=repo.workspace(); dataset=repo.dataset(workspace,"test.csv",df,"data/test.pkl"); aura=AuraOrchestrator()
    run=aura.run_analysis("descriptive statistics",df,"test.csv",measure="Revenue"); repo.analytics(workspace,dataset,"descriptive statistics",run)
    ml=aura.ml.train(df,"Target"); repo.ml(workspace,dataset,"Target",ml)
    answer=aura.answer("What is revenue?",df,"test.csv"); repo.query(workspace,dataset,"What is revenue?",answer); repo.report(workspace,dataset,[run["evidence"]["evidence_id"]],"outputs/report.pdf")
    with database.get_session() as db:
        assert db.scalar(select(MLRun).where(MLRun.dataset_id==dataset)) is not None
        assert db.scalar(select(AIQuery).where(AIQuery.dataset_id==dataset)) is not None
        assert db.scalar(select(Report).where(Report.dataset_id==dataset)) is not None
