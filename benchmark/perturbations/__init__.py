"""Controlled schema perturbations preserving AURABench analytical truth."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from benchmark.schema import BenchmarkDataset, BenchmarkGroundTruth, BenchmarkQuestion

LEVELS = ("L0", "L1", "L2", "L3", "L4", "L5")
SYNONYMS = {"revenue": "turnover", "profit": "earnings", "cost": "spend", "date/time": "calendar", "identifier": "reference", "region": "territory", "category": "segment", "quantity": "volume"}
ABBREVIATIONS = {"revenue": "rev", "profit": "pft", "cost": "cst", "date/time": "dt", "identifier": "ref", "region": "rgn", "category": "cat", "quantity": "qty"}

@dataclass
class PerturbationResult:
    dataset: BenchmarkDataset
    level: str
    column_mapping: dict[str, str]

def perturb(example: BenchmarkDataset, level: str = "L0", seed: int = 42) -> PerturbationResult:
    if level not in LEVELS:
        raise ValueError(f"Unknown perturbation level {level}")
    rng = np.random.default_rng(seed); original_roles = example.ground_truth.semantic_roles
    mapping = {column: column for column in example.frame.columns}
    if level in {"L1", "L2", "L3", "L5"}:
        vocab = SYNONYMS if level == "L1" else ABBREVIATIONS
        for index, (column, role) in enumerate(original_roles.items()):
            mapping[column] = f"field_{index + 1:02d}" if level in {"L3", "L5"} else f"{vocab.get(role, 'attribute')}_{index + 1}"
    frame = example.frame.rename(columns=mapping).copy()
    if level in {"L4", "L5"}:
        frame["misc_note"] = ["n/a" if i % 3 else "review" for i in range(len(frame))]
        frame["noise_score"] = rng.normal(0, 1, len(frame)).round(4)
    roles = {mapping[column]: role for column, role in original_roles.items()}
    questions = [BenchmarkQuestion(q.question, q.analytical_operation, [mapping.get(c, c) for c in q.source_columns], q.answerability) for q in example.ground_truth.questions]
    gt = BenchmarkGroundTruth(roles, list(example.ground_truth.applicable_kpis), questions, list(example.ground_truth.anomaly_rows))
    return PerturbationResult(BenchmarkDataset(example.family, example.seed, frame, gt, {**example.metadata, "perturbation": level}), level, mapping)
