import json

import pytest

from benchmark.independent import sha256_json, load_frozen_package
from experiments.independent_evaluation import run
from experiments.paired_statistics import paired_cluster_summary
from benchmark.quality_control import validate_package


def test_external_runner_refuses_missing_or_empty_package(tmp_path):
    result = run(tmp_path)
    assert result["status"] == "NOT_RUN"


def test_loader_keeps_labels_out_of_baseline_inputs_and_checks_checksum(tmp_path):
    records = [{"Revenue": 1}]
    (tmp_path / "manifest.json").write_text(json.dumps({"authorship": "external_human", "frozen_at": "2026-11-04T00:00:00Z"}))
    (tmp_path / "inputs.jsonl").write_text(json.dumps({"case_id": "x", "dataset_id": "d", "dataset_family": "f", "template_family": "t", "records": records, "question": "revenue", "source_sha256": sha256_json(records)}) + "\n")
    (tmp_path / "labels.jsonl").write_text(json.dumps({"case_id": "x", "answerability": "answerable", "candidate_definitions": [], "numerical_oracle": {}, "visualization_label": "valid", "dashboard_label": "consistent", "provenance_label": "verified", "adjudication_id": "j1"}) + "\n")
    (tmp_path / "annotators.jsonl").write_text("\n".join([json.dumps({"case_id": "x", "annotation_id": "a1"}), json.dumps({"case_id": "x", "annotation_id": "a2"})]) + "\n")
    (tmp_path / "adjudications.jsonl").write_text(json.dumps({"case_id": "x", "adjudication_id": "j1"}) + "\n")
    cases, labels, _ = load_frozen_package(tmp_path)
    assert cases[0].question == "revenue" and labels["x"]["answerability"] == "answerable"
    (tmp_path / "inputs.jsonl").write_text(json.dumps({"case_id": "x", "dataset_id": "d", "dataset_family": "f", "template_family": "t", "records": records, "question": "revenue", "source_sha256": "wrong"}) + "\n")
    with pytest.raises(ValueError, match="Checksum"):
        load_frozen_package(tmp_path)


def test_cluster_summary_refuses_underpowered_analysis():
    rows = [{"dataset_family": "only", "baseline": "B4", "x": 1}, {"dataset_family": "only", "baseline": "B0", "x": 0}]
    summary = paired_cluster_summary(rows, lambda row: row["x"], "B4", "B0")
    assert summary["status"] == "NOT_RUN"


def test_quality_control_detects_duplicate_question_and_split_leakage(tmp_path):
    records = [{"Revenue": 1}]
    row = {"case_id": "x", "dataset_id": "d", "dataset_family": "retail", "template_family": "total", "records": records, "question": "What is revenue?", "source_sha256": sha256_json(records)}
    manifest = {"authorship": "external_human", "frozen_at": "2026-11-04T00:00:00Z", "development_dataset_families": ["retail"]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "inputs.jsonl").write_text(json.dumps(row) + "\n")
    (tmp_path / "labels.jsonl").write_text(json.dumps({"case_id": "x", "answerability": "answerable", "candidate_definitions": [], "numerical_oracle": {}, "visualization_label": "valid", "dashboard_label": "consistent", "provenance_label": "verified", "adjudication_id": "j"}) + "\n")
    (tmp_path / "annotators.jsonl").write_text("\n".join([json.dumps({"case_id": "x", "annotation_id": "a", "annotator_id": "u1"}), json.dumps({"case_id": "x", "annotation_id": "b", "annotator_id": "u2"})]))
    (tmp_path / "adjudications.jsonl").write_text(json.dumps({"case_id": "x", "adjudication_id": "j", "adjudicator_id": "judge"}))
    report = validate_package(tmp_path)
    assert report["status"] == "INVALID"
    assert any("leakage" in error for error in report["errors"])
