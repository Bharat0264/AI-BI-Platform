"""Typed AURABench examples and immutable analytical ground truth."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import pandas as pd

@dataclass
class BenchmarkQuestion:
    question: str
    analytical_operation: str
    source_columns: list[str]
    answerability: str = "ANSWERABLE"

@dataclass
class BenchmarkGroundTruth:
    semantic_roles: dict[str, str]
    applicable_kpis: list[str]
    questions: list[BenchmarkQuestion]
    anomaly_rows: list[int] = field(default_factory=list)

@dataclass
class BenchmarkDataset:
    family: str
    seed: int
    frame: pd.DataFrame
    ground_truth: BenchmarkGroundTruth
    metadata: dict[str, Any] = field(default_factory=dict)
