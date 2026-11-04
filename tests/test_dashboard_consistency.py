"""Adversarial, independently labeled dashboards for consistency verification."""
import copy
import pandas as pd

from aura import DashboardComponent, DashboardConsistencyEngine, compute_visualization_evidence, dashboard_detection_metrics


def fixture():
    frame = pd.DataFrame({"Sales": [100.0, 200.0], "Region": ["North", "South"], "Currency": ["USD", "USD"]})
    record = compute_visualization_evidence(frame, dataset_id="d", dataset_version_id="v1", metric_column="Sales", dimension="Region")
    record["definition"]["term"] = "sales"
    component = DashboardComponent("kpi", "KPI", record["evidence_id"], "d", "v1", {"term": "sales", "measure_column": "Sales"}, "sum", {}, "all supplied rows", "USD", None, "VERIFIED", 300.0)
    return record, component


def test_valid_dashboard_publishes_and_legitimate_filtered_view_is_not_flagged():
    record, component = fixture()
    filtered = copy.deepcopy(component); filtered.component_id = "north"; filtered.directly_comparable_group = None
    filtered.filters = {"Region": ["North"]}
    # It is a separate view, so provide evidence with the same declared filter.
    filtered_record = copy.deepcopy(record); filtered_record["evidence_id"] = "north-e"; filtered_record["filters"] = {"Region": ["North"]}; filtered_record["definition"]["filters"] = {"Region": ["North"]}
    filtered.evidence_id = "north-e"
    report = DashboardConsistencyEngine().verify([component, filtered], [record, filtered_record])
    assert report["status"] == "PUBLISH_VERIFIED"
    assert report["issues"] == []


def test_adversarial_definition_scope_currency_version_and_summary_conflicts():
    record, component = fixture()
    other = copy.deepcopy(component); other.component_id = "chart"; other.directly_comparable_group = "headline"
    other.definition = {"term": "sales", "measure_column": "Gross Sales"}; other.currency = "EUR"; other.filters = {"Region": ["North"]}; other.temporal_scope = "Q1"; other.aggregation = "mean"; other.dataset_version_id = "v2"
    component.directly_comparable_group = "headline"; component.displayed_value = 999.0
    report = DashboardConsistencyEngine().verify([component, other], [record])
    codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "REJECT"
    assert {"MISLEADING_NUMERICAL_SUMMARY", "DATASET_VERSION_MISMATCH", "DEFINITION_OR_AGGREGATION_MISMATCH", "SCOPE_MISMATCH", "CURRENCY_OR_UNIT_MISMATCH", "CROSS_VIEW_DATASET_MISMATCH", "DIFFERENT_METRIC_DEFINITION", "CROSS_VIEW_CURRENCY_OR_UNIT_CONFLICT", "DIRECT_COMPARISON_SCOPE_CONFLICT", "INCONSISTENT_AGGREGATION_LEVEL"} <= codes


def test_ambiguity_and_stale_evidence_require_clarification_or_rejection():
    record, component = fixture()
    component.verification_status = "AMBIGUOUS"
    report = DashboardConsistencyEngine().verify([component], [record])
    assert report["status"] == "REQUIRE_CLARIFICATION"
    component.freshness = "STALE"
    stale = DashboardConsistencyEngine().verify([component], [record])
    assert stale["status"] == "REJECT"
    assert {item["code"] for item in stale["issues"]} == {"UNRESOLVED_AMBIGUITY", "STALE_EVIDENCE"}


def test_independent_labels_drive_precision_recall_and_coverage():
    record, component = fixture()
    valid = DashboardConsistencyEngine().verify([component], [record])
    component.displayed_value = 1.0
    invalid = DashboardConsistencyEngine().verify([component], [record])
    metrics = dashboard_detection_metrics([valid, invalid], [set(), {"MISLEADING_NUMERICAL_SUMMARY"}])
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["coverage"] == 1.0
