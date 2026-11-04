"""Contract and independent-oracle tests for EVVE."""
import copy

import pandas as pd

from aura import (EvidenceVerifier, EvidenceVerifiedVisualizationEngine, VisualizationVerifier,
                  build_visualization_specification, compute_visualization_evidence,
                  independent_series_oracle, recommend_chart_type)


def evidence():
    frame = pd.DataFrame({"Sales": [100.0, 300.0, 50.0], "Region": ["North", "South", "North"], "Currency": ["USD"] * 3,
                          "Unit": ["dollars"] * 3})
    original = frame.copy(deep=True)
    record = compute_visualization_evidence(frame, dataset_id="dataset", dataset_version_id="v1", metric_column="Sales", dimension="Region")
    pd.testing.assert_frame_equal(frame, original)
    return frame, record


def test_verified_bar_series_matches_independent_decimal_oracle():
    frame, record = evidence()
    spec = build_visualization_specification(record)
    result = VisualizationVerifier().verify(spec, [record], EvidenceVerifier())
    assert result["status"] == "VERIFIED"
    assert spec.data_series == independent_series_oracle(frame.to_dict("records"), "Sales", "Region")


def test_incorrect_values_misaligned_categories_axes_filters_and_stale_evidence_fail():
    _, record = evidence()
    verifier = VisualizationVerifier()
    bad_series = build_visualization_specification(record)
    bad_series.data_series[0]["y"] = 999.0
    assert verifier.verify(bad_series, [record])["status"] == "INVALID"
    bad_axis = build_visualization_specification(record)
    bad_axis.axes["y"] = type(bad_axis.axes["y"])(field="Profit", label="Profit")
    assert verifier.verify(bad_axis, [record])["status"] == "INVALID"
    bad_filter = build_visualization_specification(record)
    bad_filter.filters = {"Region": ["North"]}
    assert verifier.verify(bad_filter, [record])["status"] == "INVALID"
    stale = build_visualization_specification(record)
    stale.dataset_version_id = "v2"
    assert verifier.verify(stale, [record])["status"] == "INSUFFICIENT_EVIDENCE"


def test_invalid_units_log_axis_and_sankey_are_not_accepted_without_evidence():
    _, record = evidence()
    verifier = VisualizationVerifier()
    units = build_visualization_specification(record)
    units.units = "euros"
    assert verifier.verify(units, [record])["status"] == "INVALID"
    log = build_visualization_specification(record)
    log.axes["y"] = type(log.axes["y"])(field="Sales", label="Sales", scale="log")
    record_with_zero = copy.deepcopy(record)
    record_with_zero["result"]["series"][0]["y"] = 0.0
    log.data_series = record_with_zero["result"]["series"]
    assert verifier.verify(log, [record_with_zero])["status"] == "INVALID"
    sankey = build_visualization_specification(record, chart_type="sankey")
    assert verifier.verify(sankey, [record])["status"] == "UNSUPPORTED"


def test_recommendation_and_ambiguous_impact_charts_are_conditional():
    assert recommend_chart_type(dimensions=[{"kind": "categorical"}])["chart_type"] == "bar"
    assert recommend_chart_type(dimensions=[{"kind": "categorical"}], temporal=True)["chart_type"] == "line"
    impact = {"candidates": [{"evidence": {"evidence_id": "e1", "dataset_id": "d", "definition": {"measure_column": "Gross", "currency": "USD", "unit": None},
        "result": {"chart_series": {"Region": {"x": ["N"], "y": [100.0]}}}}}]}
    output = EvidenceVerifiedVisualizationEngine().conditional_from_impact(impact)
    assert output["status"] == "AMBIGUOUS"
    assert output["specifications"][0]["conditional"] is True
    assert output["specifications"][0]["verification_status"] == "AMBIGUOUS"
