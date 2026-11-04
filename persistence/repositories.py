"""Validated document repositories using stable string IDs, not exposed ObjectIds."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from pymongo.errors import DuplicateKeyError
from .mongo import get_database
from .definitions import DefinitionRepository
from .fingerprints import dataset_digest
from .lifecycle import LifecycleRepository

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid4())
def _required(document, keys):
    missing=[key for key in keys if document.get(key) in (None, "")]
    if missing: raise ValueError(f"Invalid persistence document; missing {', '.join(missing)}")

class AuraRepository(DefinitionRepository, LifecycleRepository):
    def __init__(self, database=None): self._database=database
    @property
    def db(self):
        return self._database if self._database is not None else get_database()
    def workspace(self,name="Executive Workspace"):
        item=self.db.workspaces.find_one_and_update({"name":name},{"$setOnInsert":{"workspace_id":uid(),"name":name,"settings":{},"created_at":now()},"$set":{"updated_at":now()}},upsert=True,return_document=True)
        return item["workspace_id"]
    def dataset(self,workspace_id,name,df,storage_path):
        digest=dataset_digest(name, df)
        item=self.db.datasets.find_one_and_update({"workspace_id":workspace_id,"content_hash":digest},{"$setOnInsert":{"dataset_id":uid(),"workspace_id":workspace_id,"name":name,"original_filename":name,"storage_path":str(storage_path),"content_hash":digest,"row_count":len(df),"column_count":len(df.columns),"status":"ready","created_at":now()},"$set":{"updated_at":now()}},upsert=True,return_document=True)
        return item["dataset_id"]
    def save_inspection(self,dataset_id,inspection):
        dataset=self.db.datasets.find_one({"dataset_id":dataset_id})
        if not dataset: raise ValueError("Dataset must exist before its profile is saved.")
        self.db.dataset_profiles.update_one({"dataset_id":dataset_id},{"$set":{"workspace_id":dataset["workspace_id"],"dataset_id":dataset_id,"profile":inspection["profile"],"updated_at":now()},"$setOnInsert":{"created_at":now()}},upsert=True)
        types=inspection["profile"].get("column_profile",{})
        for field in inspection["semantic_schema"]:
            self.db.semantic_schemas.update_one({"dataset_id":dataset_id,"column_name":field["column"]},{"$set":{"workspace_id":dataset["workspace_id"],"dataset_id":dataset_id,"column_name":field["column"],"physical_type":types.get(field["column"],{}).get("dtype","unknown"),"semantic_role":field["semantic_role"],"confidence":field["confidence"],"reason":field["reason"],"updated_at":now()},"$setOnInsert":{"created_at":now()}},upsert=True)
        # Restore confirmed roles after an automatic re-profile.
        for row in self.db.semantic_schemas.find({"dataset_id":dataset_id,"user_corrected_role":{"$ne":None}}):
            self.db.semantic_schemas.update_one({"_id":row["_id"]},{"$set":{"semantic_role":row["user_corrected_role"]}})
    def correct_semantics(self,dataset_id,corrections):
        for column,role in corrections.items():
            result=self.db.semantic_schemas.update_one({"dataset_id":dataset_id,"column_name":column},{"$set":{"semantic_role":role,"user_corrected_role":role,"correction_timestamp":now(),"updated_at":now()}})
            if not result.matched_count: raise ValueError(f"Unknown semantic column: {column}")
    def corrections(self,dataset_id): return {r["column_name"]:r["user_corrected_role"] for r in self.db.semantic_schemas.find({"dataset_id":dataset_id,"user_corrected_role":{"$ne":None}})}
    def evidence(self,workspace_id,dataset_id,item):
        _required(item,["evidence_id","analysis_type","method","result","timestamp"])
        doc={"evidence_id":item["evidence_id"],"workspace_id":workspace_id,"dataset_id":dataset_id,"analysis_type":item["analysis_type"],"source_columns":item.get("source_columns",[]),"filters":item.get("filters",{}),"method":item["method"],"result":item["result"],"statistical_metadata":item.get("uncertainty",{}),"created_at":item["timestamp"]}
        doc["lifecycle_version"] = 1
        for key in ("result_bindings", "definition", "semantic_corrections", "interpretation_status", "scope", "dependency_evidence_ids", "evidence_role", "report_eligible"):
            if key in item:
                doc[key] = item[key]
        try: self.db.analytics_evidence.insert_one(doc)
        except DuplicateKeyError: pass  # Evidence is immutable insert-once.
    def analytics(self,workspace_id,dataset_id,objective,run):
        self.evidence(workspace_id,dataset_id,run["evidence"])
        doc={"analytics_run_id":uid(),"workspace_id":workspace_id,"dataset_id":dataset_id,"objective":objective,"analysis_type":run["plan"]["analytical_task"],"source_columns":run["evidence"].get("source_columns",[]),"filters":run["evidence"].get("filters",{}),"aggregation":run["plan"].get("aggregations",[]),"method":run["evidence"]["method"],"result":run["evidence"]["result"],"evidence_ids":[run["evidence"]["evidence_id"]],"created_at":now()}; self.db.analytics_runs.insert_one(doc)
    def ml(self,workspace_id,dataset_id,target,run):
        self.db.ml_runs.insert_one({"ml_run_id":uid(),"workspace_id":workspace_id,"dataset_id":dataset_id,"task_type":run["task"],"target":target,"features":list(run["feature_importance"]),"model":run["model"],"preprocessing":{},"seed":42,"training_configuration":{},"metrics":run["metrics"],"feature_importance":run["feature_importance"],"artifact_reference":None,"status":"completed","created_at":now()})
    def investigation(self,workspace_id,dataset_id,evidence):
        self.evidence(workspace_id,dataset_id,evidence); result=evidence["result"]
        self.db.anomaly_investigations.insert_one({"investigation_id":uid(),"workspace_id":workspace_id,"dataset_id":dataset_id,"metric":result.get("measure"),"comparison_period":{"current":result.get("current_period"),"previous":result.get("comparison_period")},"change":result.get("change"),"verification_state":result.get("premise_verified"),"ranked_contributors":result.get("contributors",[]),"evidence_ids":[evidence["evidence_id"]],"diagnostic_notice":"Associations are non-causal diagnostic findings.","created_at":now()})
    def query(self,workspace_id,dataset_id,question,result,provider=None, *, request_definition=None, request_scope=None, recomputed_from=None):
        self._definition_scope(workspace_id, dataset_id)
        if recomputed_from:
            original = self._artifact(workspace_id, "answer", recomputed_from)
            if original["dataset_id"] != dataset_id:
                raise ValueError("Recomputation must use the original dataset snapshot.")
        if request_definition is None and result.get("definition", {}).get("selection") == "explicit":
            request_definition = {"measure_column": result["definition"]["measure_column"]}
        query_id = uid()
        self.db.ai_queries.insert_one({**{key:result[key] for key in ("definition", "alternatives", "interpretation_check", "clarification", "claims", "verification") if key in result},
            "query_id": query_id, "workspace_id":workspace_id,"dataset_id":dataset_id,"question":question,
            "plan":result["plan"], "interpreted_task":result["plan"]["analytical_task"],"answerability":result["status"],
            "response":result["answer"],"evidence_ids":[x["evidence_id"] for x in result["evidence"]],
            "provider":provider,"model":None,"created_at":now(), "lifecycle_version":1,
            "request_definition":request_definition, "request_scope":request_scope if request_scope is not None else result.get("request_scope"), "recomputed_from":recomputed_from})
        return query_id

    def report(self,workspace_id,dataset_id,evidence_ids,path, *, answer_ids=None, parent_report_ids=None,
               recomputed_from=None, filters=None):
        self._definition_scope(workspace_id, dataset_id)
        for kind, ids in (("evidence", evidence_ids), ("answer", answer_ids or []), ("report", parent_report_ids or [])):
            for artifact_id in ids:
                if self._artifact(workspace_id, kind, artifact_id)["dataset_id"] != dataset_id:
                    raise ValueError("Report dependencies must use the same dataset snapshot.")
        if recomputed_from and self._artifact(workspace_id, "report", recomputed_from)["dataset_id"] != dataset_id:
            raise ValueError("Report regeneration must use the original dataset snapshot.")
        report_id = uid()
        self.db.reports.insert_one({"report_id":report_id,"workspace_id":workspace_id,"dataset_id":dataset_id,
            "evidence_ids":list(evidence_ids),"answer_ids":list(answer_ids or []),
            "parent_report_ids":list(parent_report_ids or []),"file_reference":str(path),"created_at":now(),
            "lifecycle_version":1,"recomputed_from":recomputed_from,"filters":filters or {}})
        return report_id
