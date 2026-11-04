"""Semantic Interpretation Impact Engine (SIIE).

SIIE is a bounded diagnostic extension of conditional interpretation
comparison.  It computes only observed, deterministic consequences of each
admissible column definition; it never selects a definition or infers a
business policy from numerical agreement.
"""
from __future__ import annotations

from dataclasses import asdict
import math
import re
from typing import Any

import numpy as np
import pandas as pd

from .core import AnalyticsEvidence
from .provenance import EvidenceClaim


SIIE_VERSION = "1.0"
MAX_IMPACT_CANDIDATES = 32
ABSOLUTE_TOLERANCE = 1e-6
IMPACT_CLASSES = {
    "STABLE_TESTED_OUTPUT", "VALUE_SENSITIVE", "RANKING_SENSITIVE",
    "VISUALIZATION_SENSITIVE", "INCOMPLETE_COMPARISON",
}


def _name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _close(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0, abs_tol=ABSOLUTE_TOLERANCE)


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_)) and math.isfinite(float(value))


def _currency_status(df: pd.DataFrame, values: pd.Series) -> tuple[str | None, str | None, list[str]]:
    columns = [column for column in df.columns if _name(column) in {"currency", "currency code", "iso currency"}]
    if not columns:
        return None, None, []
    currencies: set[str] = set()
    for column in columns:
        used = df.loc[values.notna(), column]
        if used.isna().any() or not all(isinstance(code, str) and re.fullmatch(r"[A-Za-z]{3}", code.strip()) for code in used):
            return None, "MISSING_OR_INVALID_CURRENCY", columns
        currencies.update(code.strip().upper() for code in used)
    if len(currencies) != 1:
        return None, "MIXED_CURRENCY", columns
    return next(iter(currencies)), None, columns


def _unit_status(df: pd.DataFrame, values: pd.Series) -> tuple[str | None, str | None, list[str]]:
    columns = [column for column in df.columns if _name(column) in {"unit", "units", "unit of measure", "uom"}]
    if not columns:
        return None, None, []
    units: set[str] = set()
    for column in columns:
        used = df.loc[values.notna(), column]
        if used.isna().any() or not all(isinstance(unit, str) and unit.strip() for unit in used):
            return None, "MISSING_OR_INVALID_UNIT", columns
        units.update(unit.strip() for unit in used)
    if len(units) != 1:
        return None, "AMBIGUOUS_UNIT", columns
    return next(iter(units)), None, columns


def _series_shape(values: dict[str, float]) -> tuple[str, dict[str, float] | None]:
    """Return a comparable positive-total shape, otherwise disclose no shape claim."""
    total = sum(values.values())
    if not math.isfinite(total) or total <= 0:
        return "UNAVAILABLE_NONPOSITIVE_TOTAL", None
    return "NORMALIZED_SHARE", {key: value / total for key, value in values.items()}


def _candidate_result(df: pd.DataFrame, column: str, dimensions: list[str], dataset_id: str,
                      business_term: str, semantic_role: str, verifier) -> dict[str, Any]:
    if column not in df.columns:
        return {"measure_column": column, "status": "INSUFFICIENT DATA", "unsupported_conditions": ["MISSING_COLUMN"]}
    values = pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    if not values.notna().any():
        return {"measure_column": column, "status": "INSUFFICIENT DATA", "unsupported_conditions": ["NO_FINITE_NUMERIC_VALUES"]}
    currency, currency_error, currency_columns = _currency_status(df, values)
    unit, unit_error, unit_columns = _unit_status(df, values)
    errors = [error for error in (currency_error, unit_error) if error]
    if errors:
        return {"measure_column": column, "status": "INSUFFICIENT DATA", "unsupported_conditions": errors}
    result: dict[str, Any] = {
        "measure": column, "sum": float(values.sum()), "mean": float(values.mean()),
        "rows": int(len(df)), "valid_rows": int(values.notna().sum()), "excluded_rows": int(values.isna().sum()),
        "grouped": {}, "rankings": {}, "chart_series": {},
    }
    if not all(_finite_number(result[key]) for key in ("sum", "mean")):
        return {"measure_column": column, "status": "INSUFFICIENT DATA", "unsupported_conditions": ["NONFINITE_RESULT"]}
    unsupported = []
    for dimension in dimensions:
        if dimension not in df.columns:
            unsupported.append(f"MISSING_GROUP_COLUMN:{dimension}")
            continue
        if df[dimension].isna().any():
            unsupported.append(f"MISSING_GROUP_LABELS:{dimension}")
            continue
        labels = [str(label) for label in df[dimension]]
        if len(set(labels)) != df[dimension].nunique(dropna=True):
            unsupported.append(f"COLLIDING_GROUP_LABELS:{dimension}")
            continue
        grouped = df.assign(_siie_value=values).groupby(dimension)["_siie_value"].sum(min_count=1)
        if grouped.isna().any() or not all(_finite_number(value) for value in grouped):
            unsupported.append(f"NONFINITE_GROUP_RESULT:{dimension}")
            continue
        ordered = grouped.sort_values(ascending=False)
        groups = {str(key): float(value) for key, value in ordered.items()}
        high = [str(key) for key, value in ordered.items() if _close(value, ordered.iloc[0])]
        low_value = ordered.iloc[-1]
        low = [str(key) for key, value in ordered.items() if _close(value, low_value)]
        shape_kind, shape = _series_shape(groups)
        result["grouped"][dimension] = groups
        result["rankings"][dimension] = {"descending": list(groups), "highest": high, "lowest": low}
        result["chart_series"][dimension] = {"chart_type": "bar", "x": list(groups), "y": list(groups.values()),
                                               "shape_kind": shape_kind, "normalized_shape": shape}
    source_columns = [column] + dimensions + currency_columns + unit_columns
    source_columns = list(dict.fromkeys(source_columns))
    bindings = {"sum": ["sum"], "mean": ["mean"]}
    evidence = asdict(AnalyticsEvidence.create(
        dataset_id, "semantic interpretation impact", source_columns, "pandas deterministic impact aggregation", result,
        uncertainty={"causal_claim": False, "semantic_equivalence_established": False},
    ))
    evidence.update(result_bindings=bindings, interpretation_status="CONDITIONAL", definition={
        "term": business_term, "measure_column": column, "semantic_role": semantic_role,
        "aggregation": "sum and mean", "grouping_columns": dimensions, "selection": "conditional candidate",
        "currency": currency, "unit": unit, "semantic_equivalence_established": False,
    })
    claims = [EvidenceClaim.numeric(claim_text=f"sum: {result['sum']}", evidence=evidence, value=result["sum"], operation="sum").to_dict(),
              EvidenceClaim.numeric(claim_text=f"mean: {result['mean']}", evidence=evidence, value=result["mean"], operation="mean").to_dict()]
    verification = verifier.verify(claims, [evidence], source_columns).to_dict()
    return {"measure_column": column, "status": "OK" if verification["status"] == "SUPPORTED" else "UNVERIFIED",
            "source_columns": source_columns, "evidence": evidence, "computed_evidence_ids": [evidence["evidence_id"]],
            "verification": verification, "result": result, "unsupported_conditions": unsupported}


def _pair_impact(left: dict[str, Any], right: dict[str, Any], dimensions: list[str], requested_aggregation: str) -> dict[str, Any]:
    left_result, right_result = left["result"], right["result"]
    absolute = abs(left_result["sum"] - right_result["sum"])
    relative = None if _close(left_result["sum"], 0) else absolute / abs(left_result["sum"])
    aggregate_equal = _close(left_result["sum"], right_result["sum"])
    grouped_equal = ranking_changed = shape_changed = False
    compared_dimensions, unavailable = [], []
    for dimension in dimensions:
        left_groups, right_groups = left_result["grouped"].get(dimension), right_result["grouped"].get(dimension)
        if left_groups is None or right_groups is None:
            unavailable.append(dimension)
            continue
        compared_dimensions.append(dimension)
        equal = left_groups.keys() == right_groups.keys() and all(_close(left_groups[key], right_groups[key]) for key in left_groups)
        grouped_equal = grouped_equal or not equal
        left_rank, right_rank = left_result["rankings"][dimension], right_result["rankings"][dimension]
        ranking_changed = ranking_changed or left_rank != right_rank
        left_shape = left_result["chart_series"][dimension]["normalized_shape"]
        right_shape = right_result["chart_series"][dimension]["normalized_shape"]
        if left_shape is None or right_shape is None:
            unavailable.append(f"SHAPE:{dimension}")
        elif left_shape.keys() != right_shape.keys() or any(not _close(left_shape[key], right_shape[key]) for key in left_shape):
            shape_changed = True
    if ranking_changed:
        equivalence = "RANKING_DIFFERENT"
    elif not aggregate_equal:
        equivalence = "AGGREGATE_DIFFERENT"
    elif grouped_equal:
        equivalence = "AGGREGATE_EQUIVALENT_GROUPED_DIFFERENT"
    else:
        equivalence = "TESTED_OUTPUTS_EQUAL"
    requested_left, requested_right = left_result[requested_aggregation], right_result[requested_aggregation]
    requested_absolute = abs(requested_left - requested_right)
    requested_relative = None if _close(requested_left, 0) else requested_absolute / abs(requested_left)
    return {"left": left["measure_column"], "right": right["measure_column"], "aggregate": {
                "left": left_result["sum"], "right": right_result["sum"], "absolute_difference": absolute,
                "relative_difference": relative, "relative_difference_status": "DEFINED" if relative is not None else "UNDEFINED_ZERO_REFERENCE",
                "equal_within_tolerance": aggregate_equal},
            "requested_metric_difference": {"aggregation": requested_aggregation, "left": requested_left, "right": requested_right,
                "absolute_difference": requested_absolute, "relative_difference": requested_relative,
                "relative_difference_status": "DEFINED" if requested_relative is not None else "UNDEFINED_ZERO_REFERENCE"},
            "grouped_values_differ": grouped_equal,
            "ranking_changed": ranking_changed, "ranking_reversal": ranking_changed,
            "chart_shape_changed": shape_changed, "compared_dimensions": compared_dimensions,
            "unavailable_dimensions": unavailable, "output_equivalence": equivalence}


def _impact_graph(term: str, candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    nodes = [{"id": "term", "kind": "BusinessTerm", "label": term}]
    edges = []
    for index, candidate in enumerate(candidates):
        base = f"candidate:{index}"
        nodes.append({"id": base, "kind": "CandidateDefinition", "label": candidate["measure_column"]})
        edges.append({"from": "term", "to": base, "relation": "has_candidate_definition"})
        if candidate.get("status") not in {"OK", "UNVERIFIED"}:
            continue
        plan, evidence, output = base + ":plan", base + ":evidence", base + ":output"
        nodes.extend([{"id": plan, "kind": "AnalyticalPlan", "label": "aggregate/group/ranking/chart"},
                      {"id": evidence, "kind": "Evidence", "label": candidate["computed_evidence_ids"][0]},
                      {"id": output, "kind": "KPI/Chart/Result", "label": candidate["measure_column"]}])
        edges.extend([{"from": base, "to": plan, "relation": "executes"}, {"from": plan, "to": evidence, "relation": "produces"},
                      {"from": evidence, "to": output, "relation": "supports"}])
    return {"nodes": nodes, "edges": edges}


def analyze_semantic_interpretation_impact(df: pd.DataFrame, *, dataset_id: str, business_term: str,
                                            semantic_role: str, candidates: list[str], dimensions: list[str], verifier,
                                            max_candidates: int = MAX_IMPACT_CANDIDATES, requested_aggregation: str = "sum") -> dict[str, Any]:
    """Return JSON-serializable, bounded diagnostic impacts for ambiguous columns.

    The caller supplies only already-admissible candidates. The input DataFrame is
    never mutated. Unsupported candidates remain visible with reason codes.
    """
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        return {"engine": "SIIE", "version": SIIE_VERSION, "classification": ["INCOMPLETE_COMPARISON"],
                "coverage": "PARTIAL", "unsupported_conditions": ["DUPLICATE_OR_INVALID_SOURCE_COLUMNS"], "candidates": [], "pairs": [], "graph": {"nodes": [], "edges": []}}
    if not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")
    if requested_aggregation not in {"sum", "mean"}:
        raise ValueError("requested_aggregation must be sum or mean")
    executed = [_candidate_result(df, column, dimensions, dataset_id, business_term, semantic_role, verifier)
                for column in candidates[:max_candidates]]
    usable = [candidate for candidate in executed if candidate.get("status") == "OK"]
    pairs = [_pair_impact(usable[left], usable[right], dimensions, requested_aggregation)
             for left in range(len(usable)) for right in range(left + 1, len(usable))]
    partial = (not dimensions or len(candidates) > max_candidates or len(usable) != len(candidates)
               or any(pair["unavailable_dimensions"] for pair in pairs))
    classifications = set()
    if any(not pair["aggregate"]["equal_within_tolerance"] for pair in pairs): classifications.add("VALUE_SENSITIVE")
    if any(pair["ranking_changed"] for pair in pairs): classifications.add("RANKING_SENSITIVE")
    if any(pair["chart_shape_changed"] for pair in pairs): classifications.add("VISUALIZATION_SENSITIVE")
    if partial or len(usable) < 2: classifications.add("INCOMPLETE_COMPARISON")
    if not classifications: classifications.add("STABLE_TESTED_OUTPUT")
    return {"engine": "SIIE", "version": SIIE_VERSION, "business_term": business_term, "semantic_role": semantic_role,
            "classification": sorted(classifications), "coverage": "PARTIAL" if partial else "COMPLETE",
            "candidate_count": len(candidates), "executed_count": len(executed), "dimensions": dimensions,
            "requested_aggregation": requested_aggregation,
            "candidates": executed, "pairs": pairs, "graph": _impact_graph(business_term, executed),
            "notice": "Tested numerical agreement does not establish equivalent business meaning."}
