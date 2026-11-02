"""Independent arithmetic oracle; no pandas aggregation or AURA verifier reuse."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import math


def finite_numbers(values):
    out = []
    for value in values:
        if isinstance(value, bool):
            continue
        try:
            number = Decimal(str(value))
            if number.is_finite():
                out.append(number)
        except (InvalidOperation, ValueError, TypeError):
            pass
    return out


def aggregate(values, operation):
    numbers = finite_numbers(values)
    if not numbers:
        raise ValueError("No valid numeric observations")
    total = sum(numbers, Decimal(0))
    return float(total / len(numbers) if operation == "mean" else total)


def expected_output(records, measure, operation="sum", dimension=None, direction=None):
    output = {"measure": measure, "operation": operation,
              "value": aggregate([row[measure] for row in records], operation)}
    if dimension:
        groups = defaultdict(list)
        for row in records:
            groups[str(row[dimension])].append(row[measure])
        output["groups"] = {key: aggregate(values, operation) for key, values in groups.items()}
        if direction:
            value = min(output["groups"].values()) if direction == "lowest" else max(output["groups"].values())
            output["winners"] = sorted(key for key, amount in output["groups"].items() if amount == value)
            output["winning_value"] = value
    return output


def same(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    try:
        return math.isfinite(float(left)) and math.isfinite(float(right)) and math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-6)
    except (ValueError, TypeError, OverflowError):
        return False


def numeric_errors(result, expected):
    errors = []
    if result.get("status") != "OK":
        return ["No resolved answer"]
    records = result.get("evidence", [])
    if len(records) != 1:
        return ["Expected exactly one resolved evidence record"]
    actual = records[0].get("result", {})
    if actual.get("measure") != expected["measure"]:
        errors.append("Wrong measure")
    if not same(actual.get(expected["operation"]), expected["value"]):
        errors.append("Wrong aggregate")
    if "groups" in expected:
        groups = actual.get("ranking", {})
        if groups.keys() != expected["groups"].keys() or any(not same(groups.get(key), amount) for key, amount in expected["groups"].items()):
            errors.append("Wrong or incomplete group breakdown")
    if "winners" in expected:
        requested = actual.get("requested_result", {})
        winners = requested.get("ties", [requested.get("dimension")])
        if sorted(winners) != expected["winners"] or not same(requested.get("value"), expected["winning_value"]):
            errors.append("Wrong ranking winner, tie set or value")
    return errors
