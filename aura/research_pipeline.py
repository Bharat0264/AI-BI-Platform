"""Isolated end-to-end research dashboard pipeline; legacy Flask charts are unchanged."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
import pandas as pd
from .dashboard_consistency import DashboardComponent, DashboardConsistencyEngine
from .visualization_engine import EvidenceVerifiedVisualizationEngine, VisualizationVerifier, build_visualization_specification

PIPELINE_VERSION = "research-dashboard-contract-v1"

class ResearchDashboardPipeline:
    def __init__(self, orchestrator): self.orchestrator=orchestrator

    def build(self, *, df: pd.DataFrame, dataset_id: str, dataset_version_id: str, questions: list[str], corrections=None, saved_definitions=None) -> dict[str, Any]:
        items=[]; evidence=[]; components=[]; blocked=[]
        for index, question in enumerate(questions):
            answer=self.orchestrator.answer(question, df, dataset_id, corrections=corrections, saved_definitions=saved_definitions)
            item={"question":question,"answer":answer}
            items.append(item)
            if answer["status"] == "CLARIFICATION_REQUIRED":
                # Conditional EVVE contracts stay available only for inspection.
                continue
            if answer["status"] != "OK" or answer.get("verification",{}).get("status") != "SUPPORTED":
                blocked.append({"question":question,"reason":answer["status"]})
                continue
            # Core evidence predates explicit version contracts; bind this
            # pipeline view to the caller's immutable dataset version.
            analytic={**answer["evidence"][0],"dataset_version_id":dataset_version_id}; evidence.append(analytic)
            definition=answer["definition"]
            component_id=f"kpi-{index}"
            components.append(DashboardComponent(component_id,"KPI",analytic["evidence_id"],dataset_id,dataset_version_id,
                {"term":definition["term"],"measure_column":definition["measure_column"]},definition["aggregation"],analytic.get("filters",{}),definition["period"],definition.get("currency"),definition.get("unit"),"VERIFIED",analytic["result"][definition["aggregation"]]).to_dict())
            try:
                dimension=definition.get("grouping_column")
                visual=EvidenceVerifiedVisualizationEngine(self.orchestrator.verifier).build(df,dataset_id=dataset_id,dataset_version_id=dataset_version_id,metric_column=definition["measure_column"],dimension=dimension,aggregation=definition["aggregation"],filters=analytic.get("filters",{}),temporal_scope=definition["period"])
                evidence.append(visual["evidence"])
                spec=visual["specification"]
                components.append(DashboardComponent(f"chart-{index}","VISUALIZATION",visual["evidence"]["evidence_id"],dataset_id,dataset_version_id,
                    {"term":definition["term"],"measure_column":definition["measure_column"]},definition["aggregation"],visual["evidence"].get("filters",{}),definition["period"],spec.get("currency"),spec.get("units"),visual["verification"]["status"],None).to_dict())
                item["visualization"] = spec
                item["visualization_verification"] = visual["verification"]
            except (ValueError, KeyError) as error:
                blocked.append({"question":question,"reason":f"visualization: {error}"})
        consistency=DashboardConsistencyEngine().verify(components,evidence) if components else {"status":"REJECT","issues":[],"coverage":"PARTIAL","components_checked":0}
        if any(item["answer"]["status"]=="CLARIFICATION_REQUIRED" for item in items): decision="CLARIFICATION_REQUIRED"
        elif blocked or consistency["status"] != "PUBLISH_VERIFIED": decision="BLOCKED"
        else: decision="PUBLISH_VERIFIED"
        return {"contract_version":PIPELINE_VERSION,"dataset":{"dataset_id":dataset_id,"dataset_version_id":dataset_version_id},"items":items,"evidence":evidence,"components":components,"consistency":consistency,"publication_decision":decision,"blocked":blocked,
                "notice":"Developer/research contract. Conditional charts are not resolved findings; descriptive checks are non-causal."}

    @staticmethod
    def report_manifest(contract: dict[str, Any]) -> dict[str, Any]:
        """Machine-readable provenance for only a publishable contract."""
        if contract.get("publication_decision") != "PUBLISH_VERIFIED":
            raise ValueError("A research report requires PUBLISH_VERIFIED pipeline output.")
        included=[]
        for item in contract["items"]:
            answer=item["answer"]
            visualization=item.get("visualization")
            if answer.get("status") != "OK" or answer.get("verification",{}).get("status") != "SUPPORTED":
                raise ValueError("Unverified analytical item cannot enter a research report.")
            if not visualization or item.get("visualization_verification",{}).get("status") != "VERIFIED":
                raise ValueError("Unverified visualization cannot enter a research report.")
            included.append({"question":item["question"],"definition":answer["definition"],"source_columns":answer["evidence"][0]["source_columns"],"evidence_id":answer["evidence"][0]["evidence_id"],"verification":answer["verification"]["status"],"visualization":visualization,"visualization_verification":item["visualization_verification"]["status"]})
        evidence_records=[{"evidence_id":record["evidence_id"],"dataset_id":record["dataset_id"],"dataset_version_id":record.get("dataset_version_id",record["dataset_id"]),"source_columns":record.get("source_columns",[]),"filters":record.get("filters",{}),"definition":record.get("definition",{}),"result":record.get("result",{}),"result_bindings":record.get("result_bindings",{}),"method":record.get("method"),"lifecycle_dependency_evidence_ids":record.get("dependency_evidence_ids",[])} for record in contract["evidence"]]
        return {"report_id":str(uuid4()),"generated_at":datetime.now(timezone.utc).isoformat(),"research_pipeline_version":PIPELINE_VERSION,"contract_version":contract["contract_version"],"dataset":contract["dataset"],"publication_decision":contract["publication_decision"],"consistency":contract["consistency"],"included_components":included,"evidence_records":evidence_records,"excluded_components":contract.get("blocked",[]),"limitations":"Evidence binding validates computation records, not real-world business-definition truth; findings are descriptive and non-causal."}
