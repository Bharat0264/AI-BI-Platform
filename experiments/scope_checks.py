"""Independent Python-date/Decimal reference cases for structured row scopes."""
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import random
import struct

from experiments.accuracy import Case, SEEDS
from experiments.oracle import expected_output, numeric_errors, same


def select_rows(rows, scope, period=None):
    selected, positions = [], []
    for position, row in enumerate(rows):
        if any(str(row[column]) not in values for column, values in scope.get("filters", {}).items()):
            continue
        if period is not None:
            day = date.fromisoformat(row[scope["date_column"]][:10])
            if not date.fromisoformat(period["start"]) <= day <= date.fromisoformat(period["end"]):
                continue
        selected.append(row); positions.append(position)
    predicate = {"columns": {column: sorted(set(values)) for column, values in scope.get("filters", {}).items()}}
    if period is not None:
        start, end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
        predicate["date"] = {"column": scope["date_column"], "start_inclusive": start.isoformat(),
                             "end_inclusive": end.isoformat(), "end_exclusive": (end + timedelta(days=1)).isoformat(),
                             "calendar_days": (end - start).days + 1}
    encoded = b"".join(struct.pack("<q", position) for position in positions)
    return selected, {"selected_rows": len(selected), "source_rows": len(rows),
                      "row_position_sha256": sha256(encoded).hexdigest(), "predicate": predicate}


def reference(rows, scope, measure, operation):
    chosen, audit = select_rows(rows, scope, scope.get("period"))
    current = {**expected_output(chosen, measure, operation), "row_scope": audit}
    if "compare_to" not in scope:
        return current
    chosen, audit = select_rows(rows, scope, scope["compare_to"])
    baseline = {**expected_output(chosen, measure, operation), "row_scope": audit}
    difference = Decimal(str(current["value"])) - Decimal(str(baseline["value"]))
    percent = float(difference / Decimal(str(baseline["value"])) * 100) if baseline["value"] > 0 else None
    return {"periods": {"current": current, "baseline": baseline},
            "difference": float(difference), "percent_change": percent}


def audit_errors(record, expected):
    errors = []
    actual = record.get("scope", {})
    for key in ("selected_rows", "source_rows", "row_position_sha256"):
        if actual.get(key) != expected[key]:
            errors.append("Wrong row selection audit: " + key)
    filters = record.get("filters", {})
    if filters.get("columns") != expected["predicate"]["columns"]:
        errors.append("Wrong categorical predicate")
    if "date" in expected["predicate"]:
        for key, value in expected["predicate"]["date"].items():
            if filters.get("date", {}).get(key) != value:
                errors.append("Wrong date boundary: " + key)
    required = set(expected["predicate"]["columns"])
    if "date" in expected["predicate"]:
        required.add(expected["predicate"]["date"]["column"])
    if not required.issubset(record.get("source_columns", [])):
        errors.append("Missing scope source columns")
    return errors


def scoped_errors(response, expected):
    if response.get("status") != "OK":
        return ["No resolved scoped answer"]
    errors = []
    evidence = response.get("evidence", [])
    if "periods" not in expected:
        errors.extend(numeric_errors(response, expected))
        if len(evidence) == 1:
            errors.extend(audit_errors(evidence[0], expected["row_scope"]))
        return errors
    comparisons = [item for item in evidence if item.get("analysis_type") == "period comparison"]
    if len(comparisons) != 1:
        return ["Missing unique comparison evidence"]
    result = comparisons[0].get("result", {})
    for name, period in expected["periods"].items():
        start = period["row_scope"]["predicate"]["date"]["start_inclusive"]
        records = [item for item in evidence if item.get("filters", {}).get("date", {}).get("start_inclusive") == start]
        if len(records) != 1:
            errors.append("Missing unique " + name + " evidence")
            continue
        errors.extend(numeric_errors({"status": "OK", "evidence": records}, period))
        errors.extend(audit_errors(records[0], period["row_scope"]))
        if not same(result.get(name), period["value"]):
            errors.append("Wrong comparison value: " + name)
    if not same(result.get("difference"), expected["difference"]):
        errors.append("Wrong period difference")
    if expected["percent_change"] is None:
        if result.get("percent_change") is not None:
            errors.append("Misleading percentage for nonpositive baseline")
    elif not same(result.get("percent_change"), expected["percent_change"]):
        errors.append("Wrong percentage change")
    return errors


def generate_scope_cases():
    cases = []
    current = {"start": "2025-02-01", "end": "2025-02-28"}
    baseline = {"start": "2025-01-01", "end": "2025-01-31"}
    for seed in SEEDS:
        rng = random.Random(seed)
        rows = [{"Order Date": (date(2025, 1, 1) + timedelta(days=index)).isoformat(),
                 "Revenue": rng.randint(10, 2000) / 10, "Profit": rng.randint(-100, 200) / 10,
                 "Region": ["North", "South"][index % 2], "Category": ["Office", "Tools", "Food"][index % 3]} for index in range(72)]
        specifications = [
            ("region", "What is revenue?", "Revenue", "sum", {"filters": {"Region": ["North"]}}),
            ("intersection", "What is average profit?", "Profit", "mean", {"filters": {"Region": ["North"], "Category": ["Office"]}}),
            ("period", "What is revenue?", "Revenue", "sum", {"date_column": "Order Date", "period": current}),
            ("comparison", "What is revenue?", "Revenue", "sum", {"date_column": "Order Date", "period": current, "compare_to": baseline}),
            ("mean-comparison", "What is average revenue?", "Revenue", "mean", {"date_column": "Order Date", "period": current, "compare_to": baseline}),
            ("filtered-comparison", "What is revenue?", "Revenue", "sum", {"filters": {"Region": ["North"], "Category": ["Office"]}, "date_column": "Order Date", "period": current, "compare_to": baseline}),
        ]
        for name, question, measure, operation, scope in specifications:
            cases.append(Case(f"scope-{seed}-{name}", "scoped_arithmetic", seed, rows, question, "OK", reference(rows, scope, measure, operation), {"scope": scope}))
    tiny = [{"Order Date": "2025-01-01", "Revenue": 0, "Region": "North"}, {"Order Date": "2025-02-28T23:59:59", "Revenue": 20, "Region": "North"}]
    scope = {"date_column": "Order Date", "period": current, "compare_to": baseline}
    for amount, name in [(0, "zero"), (-10, "negative")]:
        rows = [{**row, "Revenue": amount if index == 0 else row["Revenue"]} for index, row in enumerate(tiny)]
        cases.append(Case("scope-" + name, "scoped_edge", -1, rows, "What is revenue?", "OK", reference(rows, scope, "Revenue", "sum"), {"scope": scope}))
    invalid = [
        (tiny, {"filters": {"Region": ["Unknown"]}}),
        (tiny, {"date_column": "Order Date", "period": {"start": "2025-04-01", "end": "2025-04-30"}}),
        (tiny, {"date_column": "Order Date", "period": current, "compare_to": current}),
        ([{**row, "Order Date": "01/02/2025"} for row in tiny], scope),
        ([{**row, "Order Date": "2025-01-01T00:00:00Z"} for row in tiny], scope),
        ([{**row, "Currency": "USD" if index == 0 else "EUR"} for index, row in enumerate(tiny)], scope),
        (tiny, {"filters": {"Revenue": ["20"]}}),
        (tiny, {"date_column": "Order Date"}),
    ]
    for index, (rows, raw) in enumerate(invalid):
        cases.append(Case(f"scope-invalid-{index}", "invalid_scope", -1, rows, "What is revenue?", "INSUFFICIENT DATA", {}, {"scope": raw}))
    return cases
