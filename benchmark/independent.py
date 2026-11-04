"""Loading and validation primitives for externally annotated frozen evaluation data.

No records ship with this module.  Developer-authored fixtures belong in
``benchmark.evaluation`` and must never be passed to this loader as independent
evaluation evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FrozenCase:
    case_id: str
    dataset_id: str
    dataset_family: str
    template_family: str
    records: list[dict[str, Any]]
    question: str
    source_sha256: str


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return sha256(canonical_json(value)).hexdigest()


def load_frozen_package(root: str | Path) -> tuple[list[FrozenCase], dict[str, Any], dict[str, Any]]:
    """Load a frozen package with system inputs and labels deliberately separate.

    Required files also preserve the two independent annotation records and an
    adjudication record for every final label.
    Labels are returned separately and are never supplied to baseline adapters.
    """
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    inputs = [json.loads(line) for line in (root / "inputs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    labels = [json.loads(line) for line in (root / "labels.jsonl").read_text(encoding="utf-8").splitlines() if line]
    annotations = [json.loads(line) for line in (root / "annotators.jsonl").read_text(encoding="utf-8").splitlines() if line]
    adjudications = [json.loads(line) for line in (root / "adjudications.jsonl").read_text(encoding="utf-8").splitlines() if line]
    if manifest.get("authorship") != "external_human" or not manifest.get("frozen_at"):
        raise ValueError("Package is not a frozen externally human-authored evaluation corpus")
    label_map = {row["case_id"]: row for row in labels}
    annotation_cases: dict[str, set[str]] = {}
    for row in annotations:
        annotation_cases.setdefault(row["case_id"], set()).add(row["annotation_id"])
    adjudication_ids = {row["adjudication_id"] for row in adjudications}
    cases: list[FrozenCase] = []
    for row in inputs:
        prohibited = {"expected_status", "expected_codes", "gold", "label"}.intersection(row)
        if prohibited:
            raise ValueError(f"System input {row.get('case_id')} contains labels: {sorted(prohibited)}")
        if row["case_id"] not in label_map:
            raise ValueError(f"Missing label for {row['case_id']}")
        required_label_fields = {"answerability", "candidate_definitions", "numerical_oracle",
                                 "visualization_label", "dashboard_label", "provenance_label", "adjudication_id"}
        missing_fields = required_label_fields.difference(label_map[row["case_id"]])
        if missing_fields:
            raise ValueError(f"Incomplete label for {row['case_id']}: {sorted(missing_fields)}")
        if len(annotation_cases.get(row["case_id"], set())) < 2:
            raise ValueError(f"Fewer than two independent annotations for {row['case_id']}")
        if label_map[row["case_id"]].get("adjudication_id") not in adjudication_ids:
            raise ValueError(f"Missing adjudication for {row['case_id']}")
        records = row["records"]
        digest = sha256_json(records)
        if digest != row["source_sha256"]:
            raise ValueError(f"Checksum mismatch for {row['case_id']}")
        cases.append(FrozenCase(row["case_id"], row["dataset_id"], row["dataset_family"],
                                row["template_family"], records, row["question"], digest))
    if not cases:
        raise ValueError("No independent cases: external evaluation is NOT RUN")
    return cases, label_map, manifest
