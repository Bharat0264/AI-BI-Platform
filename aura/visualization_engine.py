"""Evidence-Verified Visualization Engine (EVVE), an additive backend component."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from .provenance import EvidenceClaim

VERIFIED = "VERIFIED"
INVALID = "INVALID"
AMBIGUOUS = "AMBIGUOUS"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
UNSUPPORTED = "UNSUPPORTED"
CHART_TYPES = {"bar", "column", "line", "scatter", "histogram", "box", "heatmap", "treemap", "sankey", "forecast"}


@dataclass(frozen=True)
class AxisDefinition:
    field: str
    label: str
    scale: str = "linear"
    unit: str | None = None


@dataclass
class VisualizationSpecification:
    chart_type: str
    dataset_id: str
    dataset_version_id: str
    metric_definition: dict[str, Any]
    dimensions: list[str]
    aggregation: str
    filters: dict[str, Any]
    temporal_scope: dict[str, Any] | str | None
    units: str | None
    currency: str | None
    axes: dict[str, AxisDefinition]
    data_series: list[dict[str, Any]]
    evidence_references: list[str]
    verification_status: str = INSUFFICIENT_EVIDENCE
    verification: dict[str, Any] = field(default_factory=dict)
    conditional: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["axes"] = {key: asdict(axis) for key, axis in self.axes.items()}
        return value


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def _currency_and_unit(df: pd.DataFrame, values: pd.Series) -> tuple[str | None, str | None, str | None]:
    currency = unit = None
    for column in df.columns:
        normalized = str(column).lower().replace("_", " ").strip()
        used = df.loc[values.notna(), column]
        if normalized in {"currency", "currency code", "iso currency"}:
            codes = {str(value).strip().upper() for value in used.dropna()}
            if used.isna().any() or len(codes) != 1 or not all(len(code) == 3 and code.isalpha() for code in codes):
                return None, None, "INVALID_CURRENCY"
            currency = next(iter(codes))
        if normalized in {"unit", "units", "unit of measure", "uom"}:
            units = {str(value).strip() for value in used.dropna()}
            if used.isna().any() or len(units) != 1:
                return None, None, "AMBIGUOUS_UNIT"
            unit = next(iter(units))
    return currency, unit, None


def recommend_chart_type(*, dimensions: list[dict[str, str]], metric_count: int = 1, temporal: bool = False,
                         flow_fields: bool = False, forecast_intervals: bool = False, distribution: bool = False,
                         hierarchical: bool = False, box_distribution: bool = False) -> dict[str, Any]:
    """Pure deterministic recommendation; unsupported charts require explicit valid shapes."""
    kinds = [item.get("kind") for item in dimensions]
    if forecast_intervals:
        return {"chart_type": "forecast", "status": "SUPPORTED", "reason": "explicit forecast intervals"}
    if flow_fields:
        return {"chart_type": "sankey", "status": "SUPPORTED", "reason": "source, target and nonnegative flow value supplied"}
    if hierarchical and len(dimensions) >= 2:
        return {"chart_type": "treemap", "status": "SUPPORTED", "reason": "hierarchical categorical dimensions"}
    if temporal and metric_count == 1:
        return {"chart_type": "line", "status": "SUPPORTED", "reason": "time plus one metric"}
    if kinds.count("numeric") >= 2:
        return {"chart_type": "scatter", "status": "SUPPORTED", "reason": "two numeric fields"}
    if len(dimensions) == 2 and all(kind == "categorical" for kind in kinds):
        return {"chart_type": "heatmap", "status": "SUPPORTED", "reason": "two categorical dimensions"}
    if len(dimensions) == 1 and kinds[0] == "categorical":
        if box_distribution:
            return {"chart_type": "box", "status": "SUPPORTED", "reason": "categorical distribution"}
        return {"chart_type": "bar", "status": "SUPPORTED", "reason": "categorical aggregate"}
    if not dimensions:
        return {"chart_type": "histogram", "status": "SUPPORTED", "reason": "one numeric distribution" if distribution else "one numeric field"}
    return {"chart_type": None, "status": UNSUPPORTED, "reason": "no supported deterministic chart mapping"}


def compute_visualization_evidence(df: pd.DataFrame, *, dataset_id: str, dataset_version_id: str, metric_column: str,
                                   dimension: str | None = None, aggregation: str = "sum", filters: dict | None = None,
                                   temporal_scope: dict | str | None = None) -> dict[str, Any]:
    """Compute a bounded chart series before chart construction; never mutates ``df``."""
    if aggregation not in {"sum", "mean"} or metric_column not in df.columns:
        raise ValueError("A supported aggregation and existing metric column are required.")
    values = pd.to_numeric(df[metric_column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    if not values.notna().any():
        raise ValueError("Metric has no finite numeric values.")
    currency, unit, problem = _currency_and_unit(df, values)
    if problem:
        raise ValueError(problem)
    if dimension is not None:
        if dimension not in df.columns or df[dimension].isna().any():
            raise ValueError("A chart dimension must exist and have no missing labels.")
        labels = [str(item) for item in df[dimension]]
        if len(set(labels)) != df[dimension].nunique(dropna=True):
            raise ValueError("Chart labels collide after string conversion.")
        grouped = df.assign(_evve_value=values).groupby(dimension)["_evve_value"]
        grouped = grouped.sum(min_count=1) if aggregation == "sum" else grouped.mean()
        if grouped.isna().any() or not all(_finite(value) for value in grouped):
            raise ValueError("Chart series contains non-finite values.")
        series = [{"x": str(label), "y": float(value)} for label, value in grouped.sort_values(ascending=False).items()]
    else:
        series = [{"x": str(index), "y": float(value)} for index, value in enumerate(values.dropna())]
    result = {"metric": metric_column, "aggregation": aggregation, "sum": float(values.sum()), "mean": float(values.mean()),
              "series": series, "rows": int(len(df)), "valid_rows": int(values.notna().sum()), "excluded_rows": int(values.isna().sum()),
              "dataset_version_id": dataset_version_id}
    from .core import AnalyticsEvidence
    columns = [metric_column] + ([dimension] if dimension else [])
    evidence = asdict(AnalyticsEvidence.create(dataset_id, "visualization series", columns, "pandas deterministic visualization aggregation", result, filters=filters or {}, uncertainty={"causal_claim": False}))
    evidence.update(result_bindings={"sum": ["sum"], "mean": ["mean"]}, definition={"measure_column": metric_column,
        "aggregation": aggregation, "grouping_column": dimension, "filters": filters or {}, "period": temporal_scope or "all supplied rows",
        "currency": currency, "unit": unit}, dataset_version_id=dataset_version_id)
    return evidence


class VisualizationVerifier:
    """Checks a chart contract against compact deterministic evidence, not raw data."""
    def verify(self, specification: VisualizationSpecification, evidence: list[dict], evidence_verifier=None) -> dict[str, Any]:
        if specification.chart_type not in CHART_TYPES:
            return {"status": UNSUPPORTED, "reasons": ["UNSUPPORTED_CHART_TYPE"]}
        if specification.conditional and specification.verification_status == VERIFIED:
            return {"status": AMBIGUOUS, "reasons": ["CONDITIONAL_DEFINITION_NOT_SELECTED"]}
        by_id = {item.get("evidence_id"): item for item in evidence}
        if len(specification.evidence_references) != 1 or specification.evidence_references[0] not in by_id:
            return {"status": INSUFFICIENT_EVIDENCE, "reasons": ["MISSING_OR_AMBIGUOUS_EVIDENCE_REFERENCE"]}
        record = by_id[specification.evidence_references[0]]
        if record.get("dataset_id") != specification.dataset_id or record.get("dataset_version_id") != specification.dataset_version_id:
            return {"status": INSUFFICIENT_EVIDENCE, "reasons": ["DATASET_VERSION_MISMATCH"]}
        definition, result = record.get("definition", {}), record.get("result", {})
        if definition.get("measure_column") != specification.metric_definition.get("measure_column") or definition.get("aggregation") != specification.aggregation:
            return {"status": INVALID, "reasons": ["METRIC_OR_AGGREGATION_MISMATCH"]}
        if record.get("filters", {}) != specification.filters or definition.get("period") != specification.temporal_scope:
            return {"status": INVALID, "reasons": ["FILTER_OR_SCOPE_MISMATCH"]}
        if definition.get("currency") != specification.currency or definition.get("unit") != specification.units:
            return {"status": INVALID, "reasons": ["CURRENCY_OR_UNIT_MISMATCH"]}
        expected = result.get("series")
        if not isinstance(expected, list) or any(not isinstance(row, dict) or not _finite(row.get("y")) for row in expected):
            return {"status": INSUFFICIENT_EVIDENCE, "reasons": ["INVALID_EVIDENCE_SERIES"]}
        if specification.data_series != expected:
            return {"status": INVALID, "reasons": ["SERIES_VALUE_OR_ALIGNMENT_MISMATCH"]}
        if specification.chart_type in {"bar", "column", "line", "treemap"} and "x" not in specification.axes:
            return {"status": INVALID, "reasons": ["MISSING_CATEGORY_AXIS"]}
        if "y" not in specification.axes or specification.axes["y"].field != specification.metric_definition.get("measure_column"):
            return {"status": INVALID, "reasons": ["INVALID_METRIC_AXIS"]}
        if specification.axes["y"].scale not in {"linear", "log"} or (specification.axes["y"].scale == "log" and any(row["y"] <= 0 for row in expected)):
            return {"status": INVALID, "reasons": ["MISLEADING_AXIS_SCALE"]}
        if specification.chart_type == "sankey":
            return {"status": UNSUPPORTED, "reasons": ["FLOW_EVIDENCE_REQUIRED"]}
        if specification.chart_type == "forecast":
            intervals = result.get("forecast_intervals")
            if not isinstance(intervals, list) or any(not (_finite(row.get("lower")) and _finite(row.get("upper")) and row["lower"] <= row["upper"]) for row in intervals):
                return {"status": UNSUPPORTED, "reasons": ["SUPPORTED_FORECAST_INTERVALS_REQUIRED"]}
        return {"status": VERIFIED, "reasons": [], "evidence_id": record["evidence_id"]}


def build_visualization_specification(evidence: dict, *, chart_type: str = "bar", conditional: bool = False) -> VisualizationSpecification:
    """Build a chart contract solely from deterministic evidence."""
    definition, result = evidence.get("definition", {}), evidence.get("result", {})
    dimension = definition.get("grouping_column")
    return VisualizationSpecification(chart_type=chart_type, dataset_id=evidence["dataset_id"], dataset_version_id=evidence["dataset_version_id"],
        metric_definition={"measure_column": definition.get("measure_column")}, dimensions=[dimension] if dimension else [],
        aggregation=definition.get("aggregation"), filters=evidence.get("filters", {}), temporal_scope=definition.get("period"),
        units=definition.get("unit"), currency=definition.get("currency"), axes={
            "x": AxisDefinition(field=dimension or "row", label=dimension or "Row"),
            "y": AxisDefinition(field=definition.get("measure_column"), label=definition.get("measure_column"), unit=definition.get("unit"))},
        data_series=[dict(row) for row in result.get("series", [])], evidence_references=[evidence["evidence_id"]], conditional=conditional)


def independent_series_oracle(records: list[dict], metric_column: str, dimension: str, aggregation: str = "sum") -> list[dict[str, Any]]:
    """Decimal/Python oracle for tests and experiments; deliberately avoids pandas aggregation."""
    values: dict[str, list[Decimal]] = {}
    for row in records:
        try: value = Decimal(str(row[metric_column]))
        except (KeyError, InvalidOperation): continue
        if not value.is_finite(): continue
        values.setdefault(str(row[dimension]), []).append(value)
    output = []
    for label, group in values.items():
        value = sum(group) if aggregation == "sum" else sum(group) / Decimal(len(group))
        output.append({"x": label, "y": float(value)})
    return sorted(output, key=lambda row: row["y"], reverse=True)


class EvidenceVerifiedVisualizationEngine:
    def __init__(self, evidence_verifier=None):
        self.evidence_verifier = evidence_verifier
        self.verifier = VisualizationVerifier()

    def build(self, df: pd.DataFrame, **kwargs) -> dict[str, Any]:
        evidence = compute_visualization_evidence(df, **kwargs)
        specification = build_visualization_specification(evidence)
        verification = self.verifier.verify(specification, [evidence], self.evidence_verifier)
        specification.verification_status, specification.verification = verification["status"], verification
        return {"specification": specification.to_dict(), "evidence": evidence, "verification": verification}

    def conditional_from_impact(self, impact: dict[str, Any], chart_type: str = "bar") -> dict[str, Any]:
        specs = []
        for candidate in impact.get("candidates", []):
            evidence = candidate.get("evidence")
            if not evidence:
                continue
            # SIIE evidence uses a map of chart series; expose each separately but never select one.
            for dimension, series in evidence["result"].get("chart_series", {}).items():
                adapted = {**evidence, "dataset_version_id": evidence.get("dataset_version_id", evidence["dataset_id"]),
                    "definition": {**evidence["definition"], "grouping_column": dimension, "aggregation": "sum"},
                    "result": {**evidence["result"], "series": [{"x": x, "y": y} for x, y in zip(series["x"], series["y"])]}}
                spec = build_visualization_specification(adapted, chart_type=chart_type, conditional=False)
                check = self.verifier.verify(spec, [adapted])
                spec.conditional = True
                spec.verification_status = AMBIGUOUS
                spec.verification = {"status": AMBIGUOUS, "conditional_verification": check,
                                     "reason": "CANDIDATE_DEFINITION_NOT_SELECTED"}
                specs.append(spec.to_dict())
        return {"status": AMBIGUOUS, "conditional": True, "specifications": specs,
                "notice": "Each chart is conditional on its named candidate definition; none is selected."}
