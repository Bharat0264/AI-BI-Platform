"""Quality checks for externally collected AURA-BI benchmark packages."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from benchmark.independent import canonical_json, load_frozen_package, sha256_json


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_package(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    cases, labels, manifest = load_frozen_package(root)
    inputs = _jsonl(root / "inputs.jsonl")
    annotations = _jsonl(root / "annotators.jsonl")
    adjudications = _jsonl(root / "adjudications.jsonl")
    errors: list[str] = []
    seen_questions: dict[str, str] = {}
    for row in inputs:
        normalized = " ".join(row["question"].lower().split())
        if normalized in seen_questions:
            errors.append(f"duplicate question: {row['case_id']} and {seen_questions[normalized]}")
        seen_questions[normalized] = row["case_id"]
    split = manifest.get("split", "evaluation")
    development = set(manifest.get("development_dataset_families", [])) | set(manifest.get("development_template_families", []))
    for case in cases:
        if case.dataset_family in development or case.template_family in development:
            errors.append(f"development/evaluation leakage: {case.case_id}")
    for case_id, label in labels.items():
        if not label.get("adjudication_id"):
            errors.append(f"missing adjudication ID: {case_id}")
    if len({a.get("annotator_id") for a in annotations if a.get("annotator_id")}) < 2:
        errors.append("fewer than two distinct annotators")
    if len({a.get("adjudicator_id") for a in adjudications if a.get("adjudicator_id")}) < 1:
        errors.append("missing adjudicator identity")
    manifest_digest = sha256_json({k: v for k, v in manifest.items() if k != "package_sha256"})
    if manifest.get("package_sha256") and manifest["package_sha256"] != manifest_digest:
        errors.append("manifest checksum mismatch")
    disagreements = Counter()
    by_case: dict[str, list[dict[str, Any]]] = {}
    for annotation in annotations:
        if annotation.get("case_id"):
            by_case.setdefault(annotation["case_id"], []).append(annotation)
    for case_id, rows in by_case.items():
        values = {canonical_json(row.get("answerability")) for row in rows}
        if len(values) > 1:
            disagreements["answerability"] += 1
    return {"status": "VALID" if not errors else "INVALID", "split": split, "cases": len(cases),
            "errors": errors, "disagreements": dict(disagreements),
            "dataset_clusters": sorted({c.dataset_family for c in cases}),
            "template_clusters": sorted({c.template_family for c in cases})}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("package"); args = parser.parse_args()
    print(json.dumps(validate_package(args.package), indent=2))


if __name__ == "__main__": main()
