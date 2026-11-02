"""Seeded, independent numerical and coverage evaluation for the analyst endpoint."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from aura import AuraOrchestrator
from experiments.oracle import expected_output, numeric_errors
import pandas as pd

SEEDS = (42, 123, 456, 789, 2026, 3203, 4001, 5003, 6007, 7001)


@dataclass
class Case:
    case_id: str
    family: str
    seed: int
    records: list
    question: str
    expected_status: str
    expected: dict = field(default_factory=dict)
    kwargs: dict = field(default_factory=dict)


def generate_cases(seeds=SEEDS):
    cases = []
    templates = [
        ("revenue_total", "What is revenue?", "Revenue", "sum", None, None),
        ("profit_total", "What is profit?", "Profit", "sum", None, None),
        ("cost_total", "What is cost?", "Cost", "sum", None, None),
        ("quantity_total", "What is quantity?", "Quantity", "sum", None, None),
        ("revenue_mean", "What is average revenue?", "Revenue", "mean", None, None),
        ("profit_mean", "What is average profit?", "Profit", "mean", None, None),
        ("revenue_region", "What is revenue by region?", "Revenue", "sum", "Region", None),
        ("profit_category", "What is profit by category?", "Profit", "sum", "Category", None),
        ("mean_region", "What is average revenue by region?", "Revenue", "mean", "Region", None),
        ("mean_category", "What is average profit by category?", "Profit", "mean", "Category", None),
        ("highest_revenue", "Which region has the highest revenue?", "Revenue", "sum", "Region", "highest"),
        ("lowest_profit", "Which category has the lowest profit?", "Profit", "sum", "Category", "lowest"),
    ]
    capability = ["How much revenue did we earn?", "Show me revenue for each region", "What is total revenue across all regions?",
                  "Give me the average revenue per region", "Which region earned the most revenue?",
                  "Show the sum of revenue", "What is the minimum regional revenue?", "What is total profit across all categories?"]
    for seed in seeds:
        rng = random.Random(seed)
        records = [{"Revenue": rng.randint(-50000, 100000) / 100, "Profit": rng.randint(-20000, 30000) / 100,
                    "Cost": rng.randint(0, 50000) / 100, "Quantity": rng.randint(1, 20),
                    "Region": ["North", "South", "East", "West"][i % 4], "Category": ["Office", "Food", "Tools"][i % 3]} for i in range(48)]
        for label, question, measure, operation, dimension, direction in templates:
            cases.append(Case(f"{seed}-{label}", "supported_arithmetic", seed, records, question, "OK",
                              expected_output(records, measure, operation, dimension, direction)))
        # Same arithmetic, independently generated data and known business role corrections.
        corrected = [{("Amount X" if key == "Revenue" else key): value for key, value in row.items()} for row in records]
        cases.append(Case(f"{seed}-corrected", "supported_arithmetic", seed, corrected, "What is revenue?", "OK",
                          expected_output(corrected, "Amount X"), {"corrections": {"Amount X": "revenue"}}))
        dirty = [{**row, "Revenue": None if i % 11 == 0 else "invalid" if i % 13 == 0 else row["Revenue"]} for i, row in enumerate(records)]
        cases.append(Case(f"{seed}-invalid-values", "supported_arithmetic", seed, dirty, "What is revenue?", "OK", expected_output(dirty, "Revenue")))
        for index, question in enumerate(["What is revenue last month?", "Predict revenue", "Why did revenue fall?", "What is revenue in North?", "What is employee morale?", "What is profit margin?"]):
            cases.append(Case(f"{seed}-reject-{index}", "safe_refusal", seed, records, question, "INSUFFICIENT DATA"))
        ambiguous = [{"Gross Sales": row["Revenue"], "Net Sales": row["Revenue"] - abs(row["Cost"]) / 10, "Region": row["Region"]} for row in records]
        outputs = {col: expected_output(ambiguous, col) for col in ("Gross Sales", "Net Sales")}
        cases.append(Case(f"{seed}-ambiguity", "ambiguity", seed, ambiguous, "What is sales?", "CLARIFICATION_REQUIRED", {"alternatives": outputs}))
        cases.append(Case(f"{seed}-explicit", "supported_arithmetic", seed, ambiguous, "What is sales?", "OK", outputs["Net Sales"], {"definition": {"measure_column": "Net Sales"}}))
        tied = [{"Revenue": 10., "Region": name} for name in ("North", "South", "East", "West")]
        cases.append(Case(f"{seed}-ties", "supported_arithmetic", seed, tied, "Which region has the highest revenue?", "OK", expected_output(tied, "Revenue", "sum", "Region", "highest")))
        cases.append(Case(f"{seed}-missing-measure", "safe_refusal", seed, [{"Revenue": row["Revenue"]} for row in records], "What is profit?", "INSUFFICIENT DATA"))
        for index, question in enumerate(capability):
            measure = "Profit" if index == 7 else "Revenue"
            operation = "mean" if index == 3 else "sum"
            dimension = "Region" if index in (1, 3, 4, 6) else None
            direction = "highest" if index == 4 else "lowest" if index == 6 else None
            cases.append(Case(f"{seed}-capability-{index}", "ordinary_phrasing", seed, records, question, "OK", expected_output(records, measure, operation, dimension, direction)))
    # Fixed adversarial fixtures are separate from seeded arithmetic cases.
    fixtures = [
        ("percent_symbol", [{"Revenue %": 20}, {"Revenue %": 30}], "What is revenue?", "INSUFFICIENT DATA", {}),
        ("boolean_amount", [{"Revenue": True}, {"Revenue": False}], "What is revenue?", "INSUFFICIENT DATA", {}),
        ("mixed_currencies", [{"Revenue": 10, "Currency": "USD"}, {"Revenue": 20, "Currency": "EUR"}], "What is revenue?", "INSUFFICIENT DATA", {}),
        ("missing_currency", [{"Revenue": 10, "Currency": "USD"}, {"Revenue": 20, "Currency": None}], "What is revenue?", "INSUFFICIENT DATA", {}),
        ("group_label_collision", [{"Revenue": 10, "Region": 1}, {"Revenue": 20, "Region": "1"}], "What is revenue by region?", "INSUFFICIENT DATA", {"corrections": {"Region": "region"}}),
        ("empty_values", [{"Revenue": None}, {"Revenue": None}], "What is revenue?", "INSUFFICIENT DATA", {}),
        ("infinite_values", [{"Revenue": float("inf")}, {"Revenue": float("-inf")}], "What is revenue?", "INSUFFICIENT DATA", {}),
        ("partial_groups", [{"Revenue": 10, "Region": "North"}, {"Revenue": 20, "Region": None}], "What is revenue by region?", "INSUFFICIENT DATA", {}),
        ("margin_amount", [{"Profit Margin": 0.1}, {"Profit Margin": 0.2}], "What is profit?", "INSUFFICIENT DATA", {}),
        ("numeric_strings", [{"Revenue": "10.25"}, {"Revenue": "-1.50"}], "What is revenue?", "OK", {}),
        ("single_currency", [{"Revenue": 10, "Currency": "USD"}, {"Revenue": 20, "Currency": "USD"}], "What is revenue?", "OK", {}),
        ("quantity_mixed_currency", [{"Quantity": 10, "Currency": "USD"}, {"Quantity": 20, "Currency": "EUR"}], "What is quantity?", "OK", {}),
    ]
    for label, records, question, status, kwargs in fixtures:
        expected = expected_output(records, "Quantity" if label == "quantity_mixed_currency" else "Revenue") if status == "OK" else {}
        cases.append(Case(label, "adversarial", -1, records, question, status, expected, kwargs))
    return cases


def assess(case, response):
    errors = []
    if response.get("status") != case.expected_status:
        errors.append(f"Expected {case.expected_status}, got {response.get('status')}")
    if case.expected_status == "OK":
        if "row_scope" in case.expected or "periods" in case.expected:
            from experiments.scope_checks import scoped_errors
            errors.extend(scoped_errors(response, case.expected))
        else:
            errors.extend(numeric_errors(response, case.expected))
    elif case.expected_status == "INSUFFICIENT DATA" and response.get("evidence"):
        errors.append("Refusal returned evidence as if a result were available")
    elif case.expected_status == "CLARIFICATION_REQUIRED":
        alternatives = response.get("alternatives", [])
        by_column = {item["measure_column"]: item for item in alternatives}
        if by_column.keys() != case.expected["alternatives"].keys():
            errors.append("Missing or unexpected interpretation")
        for column, expected in case.expected["alternatives"].items():
            item = by_column.get(column, {})
            evidence = [e for e in response.get("evidence", []) if e["evidence_id"] in item.get("evidence_ids", [])]
            errors.extend(f"{column}: {error}" for error in numeric_errors({"status": item.get("status"), "evidence": evidence}, expected))
    return errors


def execute(cases):
    engine = AuraOrchestrator()
    rows = []
    for case in cases:
        start = time.perf_counter()
        exception = None
        try:
            response = engine.answer(case.question, pd.DataFrame(case.records), "accuracy-evaluation", **case.kwargs)
            errors = assess(case, response)
        except Exception as error:
            response = {"status": "EXCEPTION", "evidence": []}
            exception = type(error).__name__ + ": " + str(error)
            errors = [exception]
        rows.append({"case_id": case.case_id, "family": case.family, "seed": case.seed,
                     "question": case.question, "expected_status": case.expected_status,
                     "actual_status": response["status"], "passed": not errors, "errors": errors,
                     "expected": case.expected, "actual_evidence": response.get("evidence", []),
                     "latency_seconds": time.perf_counter() - start, "exception": exception})
    return rows


def summarize(rows):
    def block(items):
        answered = [row for row in items if row["expected_status"] == "OK"]
        returned = [row for row in answered if row["actual_status"] == "OK"]
        unsafe = [row for row in items if row["expected_status"] != "OK" and row["actual_status"] == "OK"]
        return {"cases": len(items), "passed": sum(row["passed"] for row in items),
                "failed": sum(not row["passed"] for row in items),
                "answerable_cases": len(answered), "resolved_answers": len(returned),
                "correct_resolved_answers": sum(row["passed"] for row in returned),
                "wrong_resolved_answers": sum(not row["passed"] for row in returned),
                "coverage": len(returned) / len(answered) if answered else None,
                "numeric_accuracy_when_answered": sum(row["passed"] for row in returned) / len(returned) if returned else None,
                "unsafe_unconditional_answers": len(unsafe),
                "unexpected_exceptions": sum(row["exception"] is not None for row in items)}
    return {"overall": block(rows), "by_family": {family: block([r for r in rows if r["family"] == family]) for family in sorted({r["family"] for r in rows})},
            "failure_reasons": dict(Counter(error for row in rows for error in row["errors"]))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "experiments" / "independent_accuracy")
    parser.add_argument("--suite", choices=("base", "language", "scope"), default="base")
    args = parser.parse_args()
    if args.suite == "language":
        from experiments.language_checks import generate_language_cases
        cases = generate_language_cases()
    elif args.suite == "scope":
        from experiments.scope_checks import generate_scope_cases
        cases = generate_scope_cases()
    else:
        cases = generate_cases()
    rows = execute(cases)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    source_files = ["aura/core.py", "aura/verifier.py", "aura/interpretations.py", "aura/questions.py", "aura/scopes.py", "aura/scoped_engine.py", "experiments/oracle.py", "experiments/accuracy.py"]
    if args.suite == "language":
        source_files.append("experiments/language_checks.py")
    if args.suite == "scope":
        source_files.append("experiments/scope_checks.py")
    metadata = {"run_id": stamp, "suite": args.suite, "seeds": list(SEEDS) if args.suite in {"base", "scope"} else [0], "python": sys.version,
                "packages": {name: version(name) for name in ("pandas", "numpy", "scikit-learn")},
                "source_hashes": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in source_files},
                "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "scope": "Synthetic, developer-designed cases; not independent authorship or real-user validation. Templates share seeded datasets; do not treat cases as independent statistical samples."}
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"metadata": metadata, "summary": summarize(rows), "records": rows}
    # Non-finite input fixtures are not serialized; raw results must always be JSON-safe.
    target = args.output / f"{args.suite}-{stamp}.json"
    target.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"report": str(target), "summary": report["summary"]}))


if __name__ == "__main__":
    main()
