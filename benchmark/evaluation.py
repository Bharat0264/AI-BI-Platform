"""Developer-authored stress cases for SIIE/EVVE/dashboard research.

These cases are evaluation fixtures, not external validation or independent
human authorship.  They are deliberately separate from experiments.accuracy.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    split: str
    dataset_family: str
    template_family: str
    records: list[dict[str, Any]]
    question: str
    expected_status: str
    expected_codes: tuple[str, ...] = ()


def development_stress_cases() -> list[EvaluationCase]:
    """Dataset/template-separated *development* cases, never independent evidence."""
    return [
        EvaluationCase("devstress-retail-unambiguous", "development_stress", "retail_alpha", "unambiguous_total",
            [{"Revenue": 100, "Region": "N"}, {"Revenue": 50, "Region": "S"}], "What is revenue?", "OK"),
        EvaluationCase("devstress-commerce-equal-total", "development_stress", "commerce_beta", "equal_total_breakdown",
            [{"Gross Sales": 100, "Net Sales": 200, "Region": "N"}, {"Gross Sales": 300, "Net Sales": 200, "Region": "S"}], "What is sales?", "CLARIFICATION_REQUIRED", ("RANKING_SENSITIVE",)),
        EvaluationCase("devstress-finance-ranking", "development_stress", "finance_gamma", "ranking_reversal",
            [{"Gross Sales": 400, "Net Sales": 100, "Region": "N"}, {"Gross Sales": 100, "Net Sales": 400, "Region": "S"}], "What is sales?", "CLARIFICATION_REQUIRED", ("RANKING_SENSITIVE", "VISUALIZATION_SENSITIVE")),
        EvaluationCase("devstress-logistics-currency", "development_stress", "logistics_delta", "mixed_currency",
            [{"Gross Sales": 10, "Net Sales": 9, "Currency": "USD", "Region": "N"}, {"Gross Sales": 20, "Net Sales": 18, "Currency": "EUR", "Region": "S"}], "What is sales?", "INSUFFICIENT DATA"),
        EvaluationCase("devstress-marketing-corrupt", "development_stress", "marketing_epsilon", "corrupted_values",
            [{"Revenue": "bad", "Region": "N"}, {"Revenue": None, "Region": "S"}], "What is revenue?", "INSUFFICIENT DATA"),
        EvaluationCase("devstress-energy-unsupported", "development_stress", "energy_zeta", "unsupported_request",
            [{"Revenue": 10, "Region": "N"}], "Why did revenue fall?", "INSUFFICIENT DATA"),
        # Development cases are exported for provenance but excluded from default scoring.
        EvaluationCase("devstress-misleading-schema", "development_stress", "dev_only", "misleading_schema",
            [{"Revenue %": 1, "Region": "N"}], "What is revenue?", "INSUFFICIENT DATA"),
    ]


def decimal_total(records: list[dict[str, Any]], column: str) -> float | None:
    """Standalone Decimal oracle that does not inspect AURA outputs."""
    values = []
    for row in records:
        try: value = Decimal(str(row[column]))
        except (KeyError, InvalidOperation): continue
        if value.is_finite(): values.append(value)
    return float(sum(values)) if values else None


def split_manifest(cases=None) -> dict[str, Any]:
    cases = cases or development_stress_cases()
    return {"development_stress_case_ids": [case.case_id for case in cases],
            "development_dataset_families": sorted({case.dataset_family for case in cases}),
            "development_template_families": sorted({case.template_family for case in cases}),
            "independent_evaluation_case_ids": [],
            "external_public_datasets": "None in this synthetic package; use experiments.real_data separately.",
            "leakage_policy": "These Codex/developer-authored cases are development stress tests. Independent evaluation must be loaded only from a frozen external annotation package."}


# Compatibility alias.  It does not denote independently held-out evidence.
heldout_cases = development_stress_cases
