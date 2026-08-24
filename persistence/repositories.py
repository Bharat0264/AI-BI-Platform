"""Small repositories that keep Flask handlers free of persistence details."""
from __future__ import annotations
import hashlib
from datetime import datetime
from pathlib import Path
from sqlalchemy import select
from .database import get_session
from .models import Workspace, Dataset, DatasetProfile, SemanticColumn, AnalyticsRun, Evidence, MLRun, AnomalyInvestigation, AIQuery, Report

class AuraRepository:
    def workspace(self, name="Executive Workspace"):
        with get_session() as db:
            item=db.scalar(select(Workspace).where(Workspace.name==name))
            if not item:
                item=Workspace(name=name); db.add(item); db.commit(); db.refresh(item)
            return item.id
    def dataset(self, workspace_id, name, df, storage_path):
        digest=hashlib.sha256(f"{name}|{len(df)}|{list(df.columns)}".encode()).hexdigest()
        with get_session() as db:
            item=db.scalar(select(Dataset).where(Dataset.workspace_id==workspace_id, Dataset.content_hash==digest))
            if not item:
                item=Dataset(workspace_id=workspace_id,name=name,original_filename=name,storage_path=str(storage_path),content_hash=digest,row_count=len(df),column_count=len(df.columns)); db.add(item); db.commit(); db.refresh(item)
            return item.id
    def save_inspection(self, dataset_id, inspection):
        with get_session() as db:
            profile=db.scalar(select(DatasetProfile).where(DatasetProfile.dataset_id==dataset_id))
            if profile: profile.profile=inspection["profile"]
            else: db.add(DatasetProfile(dataset_id=dataset_id,profile=inspection["profile"]))
            for field in inspection["semantic_schema"]:
                row=db.scalar(select(SemanticColumn).where(SemanticColumn.dataset_id==dataset_id,SemanticColumn.column_name==field["column"]))
                if row:
                    # Never overwrite a user-confirmed role during re-analysis.
                    if not row.user_corrected_role: row.semantic_role, row.confidence, row.reason=field["semantic_role"],field["confidence"],field["reason"]
                else: db.add(SemanticColumn(dataset_id=dataset_id,column_name=field["column"],physical_type="unknown",semantic_role=field["semantic_role"],confidence=field["confidence"],reason=field["reason"]))
            db.commit()
    def correct_semantics(self,dataset_id,corrections):
        from .models import utcnow
        with get_session() as db:
            for column,role in corrections.items():
                row=db.scalar(select(SemanticColumn).where(SemanticColumn.dataset_id==dataset_id,SemanticColumn.column_name==column))
                if row: row.user_corrected_role=row.semantic_role=role; row.correction_at=utcnow()
            db.commit()
    def corrections(self,dataset_id):
        with get_session() as db:
            rows=db.scalars(select(SemanticColumn).where(SemanticColumn.dataset_id==dataset_id,SemanticColumn.user_corrected_role.is_not(None))).all()
            return {r.column_name:r.user_corrected_role for r in rows}
    def evidence(self,workspace_id,dataset_id,item):
        with get_session() as db:
            if not db.get(Evidence,item["evidence_id"]): db.add(Evidence(evidence_id=item["evidence_id"],workspace_id=workspace_id,dataset_id=dataset_id,analysis_type=item["analysis_type"],source_columns=item["source_columns"],filters=item["filters"],method=item["method"],result=item["result"],uncertainty=item["uncertainty"],created_at=datetime.fromisoformat(item["timestamp"])))
            db.commit()
    def analytics(self,workspace_id,dataset_id,objective,run):
        self.evidence(workspace_id,dataset_id,run["evidence"])
        with get_session() as db: db.add(AnalyticsRun(workspace_id=workspace_id,dataset_id=dataset_id,objective=objective,analysis_type=run["plan"]["analytical_task"],configuration=run["plan"],result_metadata=run["evidence"]["result"])); db.commit()
    def ml(self,workspace_id,dataset_id,target,run):
        with get_session() as db: db.add(MLRun(workspace_id=workspace_id,dataset_id=dataset_id,task_type=run["task"],target=target,model=run["model"],metrics=run["metrics"],feature_importance=run["feature_importance"],configuration={"random_seed":42},status="completed")); db.commit()
    def investigation(self,workspace_id,dataset_id,evidence):
        self.evidence(workspace_id,dataset_id,evidence)
        result=evidence["result"]
        with get_session() as db: db.add(AnomalyInvestigation(workspace_id=workspace_id,dataset_id=dataset_id,metric=result.get("measure"),comparison={"current":result.get("current_period"),"previous":result.get("comparison_period"),"verified":result.get("premise_verified")},contributors=result.get("contributors",[]),evidence_id=evidence["evidence_id"])); db.commit()
    def query(self,workspace_id,dataset_id,question,result,provider=None):
        with get_session() as db: db.add(AIQuery(workspace_id=workspace_id,dataset_id=dataset_id,question=question,interpreted_task=result["plan"]["analytical_task"],answerability=result["status"],response=result["answer"],evidence_ids=[x["evidence_id"] for x in result["evidence"]],provider=provider)); db.commit()
    def report(self,workspace_id,dataset_id,evidence_ids,path):
        with get_session() as db: db.add(Report(workspace_id=workspace_id,dataset_id=dataset_id,evidence_ids=evidence_ids,file_path=str(path))); db.commit()
