"""Developer-only deterministic smoke workflow; not research evaluation."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from aura import (AuraOrchestrator, DashboardComponent, DashboardConsistencyEngine,
                  EvidenceVerifier, VisualizationVerifier, build_visualization_specification,
                  compute_visualization_evidence)

def run() -> dict:
    analyst=AuraOrchestrator()
    ordinary=pd.DataFrame({"Revenue":[100,200,300],"Profit":[10,20,30],"Region":["North","South","North"]})
    ambiguous=pd.DataFrame({"Gross Sales":[100,300],"Net Sales":[200,200],"Region":["North","South"]})
    total=analyst.answer("What is revenue?", ordinary, "developer-ordinary")
    grouped=analyst.answer("Which region has the highest revenue?", ordinary, "developer-ordinary")
    ambiguous_result=analyst.answer("What is sales by region?", ambiguous, "developer-ambiguous")
    refusal=analyst.answer("Why did revenue decline?", ordinary, "developer-ordinary")
    chart_evidence=compute_visualization_evidence(ordinary, dataset_id="developer-ordinary", dataset_version_id="v1", metric_column="Revenue", dimension="Region")
    chart=build_visualization_specification(chart_evidence)
    chart_check=VisualizationVerifier().verify(chart,[chart_evidence],EvidenceVerifier())
    component=DashboardComponent("revenue-kpi","KPI",chart_evidence["evidence_id"],"developer-ordinary","v1", {"term":"revenue","measure_column":"Revenue"},"sum",{},"all supplied rows",None,None,"VERIFIED",600.0)
    dashboard=DashboardConsistencyEngine().verify([component],[chart_evidence])
    checks={
        "total_verified": total["status"]=="OK" and total["claims"][0]["computed_value"]==600 and total["verification"]["status"]=="SUPPORTED",
        "ranking_verified": grouped["status"]=="OK" and grouped["claims"][0]["computed_value"]==400,
        "ambiguity_conditional": ambiguous_result["status"]=="CLARIFICATION_REQUIRED" and "semantic_interpretation_impact" in ambiguous_result and ambiguous_result["conditional_visualizations"]["status"]=="AMBIGUOUS",
        "refusal_safe": refusal["status"]=="INSUFFICIENT DATA" and not refusal["evidence"],
        "chart_verified": chart_check["status"]=="VERIFIED",
        "dashboard_verified": dashboard["status"]=="PUBLISH_VERIFIED",
    }
    return {"classification":"DEVELOPER_ONLY_NOT_INDEPENDENT_EVALUATION","checks":checks,"all_passed":all(checks.values()),
            "responses":{"total":total,"ranking":grouped,"ambiguous":ambiguous_result,"refusal":refusal},
            "chart_verification":chart_check,"dashboard":dashboard}

if __name__=="__main__": print(json.dumps(run(),indent=2,default=str))
