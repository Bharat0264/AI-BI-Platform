"""Developer-only end-to-end research contract tests, not benchmark evaluation."""
import copy
import pandas as pd
from aura import AuraOrchestrator, ResearchDashboardPipeline, DashboardConsistencyEngine

def frame(): return pd.DataFrame({"Revenue":[100,300],"Gross Sales":[100,300],"Net Sales":[200,200],"Region":["North","South"]})

def pipeline(): return ResearchDashboardPipeline(AuraOrchestrator())

def test_verified_pipeline_publishes_and_preserves_contract_ids():
    result=pipeline().build(df=frame()[["Revenue","Region"]],dataset_id="d",dataset_version_id="v1",questions=["What is revenue by region?"])
    assert result["publication_decision"]=="PUBLISH_VERIFIED"
    assert all(item["dataset_id"]=="d" for item in result["evidence"])
    assert all(item["dataset_version_id"]=="v1" for item in result["evidence"])

def test_ambiguity_requires_clarification_and_unsupported_is_blocked():
    ambiguous=pipeline().build(df=frame(),dataset_id="d",dataset_version_id="v1",questions=["What is sales by region?"])
    assert ambiguous["publication_decision"]=="CLARIFICATION_REQUIRED"
    assert ambiguous["items"][0]["answer"]["conditional_visualizations"]["status"]=="AMBIGUOUS"
    blocked=pipeline().build(df=frame(),dataset_id="d",dataset_version_id="v1",questions=["Why did revenue decline?"])
    assert blocked["publication_decision"]=="BLOCKED"

def test_invalid_chart_scope_currency_stale_and_missing_evidence_are_blocked():
    result=pipeline().build(df=frame()[["Revenue","Region"]],dataset_id="d",dataset_version_id="v1",questions=["What is revenue by region?"])
    components=copy.deepcopy(result["components"]); components[1]["currency"]="EUR"; components[1]["freshness"]="STALE"; components[1]["filters"]={"Region":["North"]}
    components[1]["directly_comparable_group"]="same";components[0]["directly_comparable_group"]="same"
    report=DashboardConsistencyEngine().verify(components,result["evidence"])
    codes={issue["code"] for issue in report["issues"]}
    assert report["status"]=="REJECT"
    assert {"CURRENCY_OR_UNIT_MISMATCH","STALE_EVIDENCE","SCOPE_MISMATCH","DIRECT_COMPARISON_SCOPE_CONFLICT"} <= codes
