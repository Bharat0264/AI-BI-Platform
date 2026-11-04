"""Independent arithmetic checks for the Semantic Interpretation Impact Engine."""
import pandas as pd

from aura import AuraOrchestrator, EvidenceVerifier, analyze_semantic_interpretation_impact


def impact(df, candidates=("Gross Sales", "Net Sales"), maximum=32):
    return analyze_semantic_interpretation_impact(
        df, dataset_id="impact-test", business_term="sales", semantic_role="revenue", candidates=list(candidates),
        dimensions=["Region", "Category"], verifier=EvidenceVerifier(), max_candidates=maximum,
    )


def test_equal_totals_expose_group_and_chart_impact_without_mutation():
    frame = pd.DataFrame({"Gross Sales": [100.0, 300.0, 50.0, 50.0], "Net Sales": [300.0, 100.0, 50.0, 50.0],
                          "Region": ["North", "South", "North", "South"], "Category": ["A", "A", "B", "B"]})
    original = frame.copy(deep=True)
    report = impact(frame)
    pair = report["pairs"][0]
    assert pair["aggregate"]["left"] == 500.0
    assert pair["aggregate"]["right"] == 500.0
    assert pair["aggregate"]["equal_within_tolerance"] is True
    assert pair["grouped_values_differ"] is True
    assert pair["ranking_reversal"] is True
    assert pair["chart_shape_changed"] is True
    assert "RANKING_SENSITIVE" in report["classification"]
    assert "VISUALIZATION_SENSITIVE" in report["classification"]
    assert "STABLE_TESTED_OUTPUT" not in report["classification"]
    assert len(report["graph"]["nodes"]) >= 9
    for candidate in report["candidates"]:
        assert candidate["verification"]["status"] == "SUPPORTED"
    pd.testing.assert_frame_equal(frame, original)


def test_value_sensitive_requested_difference_and_verifiable_evidence():
    frame = pd.DataFrame({"Gross Sales": [100.0, 200.0], "Net Sales": [90.0, 150.0],
                          "Region": ["North", "South"], "Category": ["A", "B"]})
    report = impact(frame)
    pair = report["pairs"][0]
    assert pair["aggregate"]["absolute_difference"] == 60.0
    assert pair["requested_metric_difference"]["absolute_difference"] == 60.0
    assert pair["output_equivalence"] == "AGGREGATE_DIFFERENT"
    assert "VALUE_SENSITIVE" in report["classification"]
    for candidate in report["candidates"]:
        for claim in candidate["verification"]["claims"]:
            assert EvidenceVerifier().verify([claim], [candidate["evidence"]]).status == "SUPPORTED"


def test_partial_coverage_and_unsupported_conditions_are_explicit():
    columns = {f"Sales {index}": [float(index), float(index + 1)] for index in range(33)}
    columns.update({"Region": ["North", "South"], "Category": ["A", None]})
    report = analyze_semantic_interpretation_impact(pd.DataFrame(columns), dataset_id="impact-test", business_term="sales",
        semantic_role="revenue", candidates=[f"Sales {index}" for index in range(33)], dimensions=["Region", "Category"],
        verifier=EvidenceVerifier())
    assert report["coverage"] == "PARTIAL"
    assert report["executed_count"] == 32
    assert "INCOMPLETE_COMPARISON" in report["classification"]
    assert all("MISSING_GROUP_LABELS:Category" in item["unsupported_conditions"] for item in report["candidates"])


def test_mixed_currency_and_ambiguous_units_are_not_compared():
    frame = pd.DataFrame({"Gross Sales": [100.0, 200.0], "Net Sales": [90.0, 150.0],
                          "Currency": ["USD", "EUR"], "Unit": ["dollars", "euros"],
                          "Region": ["North", "South"], "Category": ["A", "B"]})
    report = impact(frame)
    assert report["pairs"] == []
    assert report["classification"] == ["INCOMPLETE_COMPARISON"]
    assert all("MIXED_CURRENCY" in item["unsupported_conditions"] for item in report["candidates"])
    assert all("AMBIGUOUS_UNIT" in item["unsupported_conditions"] for item in report["candidates"])


def test_existing_conditional_comparison_exposes_siie_report():
    frame = pd.DataFrame({"Gross Sales": [100.0, 300.0], "Net Sales": [300.0, 100.0], "Region": ["North", "South"]})
    response = AuraOrchestrator().answer("What is sales?", frame, "impact-answer")
    report = response["semantic_interpretation_impact"]
    assert response["status"] == "CLARIFICATION_REQUIRED"
    assert report["business_term"] == "sales"
    assert "RANKING_SENSITIVE" in report["classification"]
    assert response["conditional_visualizations"]["status"] == "AMBIGUOUS"
    assert all(item["conditional"] for item in response["conditional_visualizations"]["specifications"])
    assert all(item["interpretation_status"] == "CONDITIONAL" for item in response["evidence"])
