"""Tests that evaluation can detect wrong arithmetic despite supported claims."""
from copy import deepcopy
from dataclasses import asdict

import pandas as pd
import pytest

from aura import AuraOrchestrator
from experiments.accuracy import assess, generate_cases, summarize
from experiments.oracle import aggregate, expected_output, numeric_errors
from experiments.framework import evaluate_example
from benchmark.generate import generate_family


def test_oracle_is_independent_decimal_arithmetic():
    assert aggregate(["0.1", "0.2", None, "bad", float("inf"), True], "sum") == .3
    assert aggregate(["0.1", "0.2"], "mean") == .15
    assert expected_output([{"Revenue": 10, "Region": "A"}, {"Revenue": -5, "Region": "B"}], "Revenue", "sum", "Region", "lowest")["winners"] == ["B"]


def test_wrong_value_cannot_pass_by_returning_ok_and_supported():
    case = generate_cases((42,))[0]
    actual = AuraOrchestrator().answer(case.question, pd.DataFrame(case.records))
    assert not assess(case, actual)
    corrupted = deepcopy(actual)
    corrupted["evidence"][0]["result"]["sum"] += 1
    assert corrupted["status"] == "OK" and corrupted["verification"]["status"] == "SUPPORTED"
    assert "Wrong aggregate" in assess(case, corrupted)


def test_group_corruption_and_missing_ties_are_detected():
    rows = [{"Revenue": 10, "Region": "A"}, {"Revenue": 10, "Region": "B"}]
    expected = expected_output(rows, "Revenue", "sum", "Region", "highest")
    response = AuraOrchestrator().answer("Which region has the highest revenue?", pd.DataFrame(rows))
    assert numeric_errors(response, expected) == []
    response["evidence"][0]["result"]["ranking"]["A"] = 1
    response["evidence"][0]["result"]["requested_result"].pop("ties")
    errors = numeric_errors(response, expected)
    assert "Wrong or incomplete group breakdown" in errors
    assert "Wrong ranking winner, tie set or value" in errors


def test_generated_matrix_is_reproducible_and_includes_coverage_failures():
    first, second = generate_cases((42,)), generate_cases((42,))
    assert [asdict(case) for case in first] == [asdict(case) for case in second]
    assert len({case.case_id for case in first}) == len(first)
    broad = [case for case in first if case.family == "ordinary_phrasing"]
    assert broad and all(case.expected_status == "OK" for case in broad)
    # Unsupported syntax is a coverage failure, not a benchmark-safe-refusal success.
    assert assess(broad[0], {"status": "INSUFFICIENT DATA", "evidence": []})


@pytest.mark.parametrize("records,question", [
    ([{"Revenue %": 20}, {"Revenue %": 30}], "What is revenue?"),
    ([{"Revenue": True}, {"Revenue": False}], "What is revenue?"),
    ([{"Revenue": 10, "Currency": "USD"}, {"Revenue": 20, "Currency": "EUR"}], "What is revenue?"),
    ([{"Revenue": 10, "Currency": "USD"}, {"Revenue": 20, "Currency": None}], "What is revenue?"),
    ([{"Revenue": 10, "Region": 1}, {"Revenue": 20, "Region": "1"}], "What is revenue by region?"),
])
def test_unsafe_amount_and_grouping_cases_refuse(records, question):
    result = AuraOrchestrator().answer(question, pd.DataFrame(records))
    assert result["status"] == "INSUFFICIENT DATA"
    assert result["evidence"] == []


def test_currency_scope_is_recorded_and_quantity_does_not_require_conversion():
    df = pd.DataFrame({"Revenue": [10, 20], "Currency": ["usd", "USD"], "Quantity": [1, 2]})
    result = AuraOrchestrator().answer("What is revenue?", df)
    assert result["status"] == "OK"
    assert result["definition"]["currency"] == "USD"
    assert result["evidence"][0]["source_columns"] == ["Revenue", "Currency"]
    df.loc[0, "Currency"] = "EUR"
    quantity = AuraOrchestrator().answer("What is quantity?", df)
    assert quantity["status"] == "OK"
    assert quantity["claims"][0]["computed_value"] == 3


def test_empty_answer_coverage_does_not_report_perfect_numeric_accuracy():
    summary = summarize([{"expected_status": "OK", "actual_status": "INSUFFICIENT DATA", "passed": False,
                          "family": "test", "errors": ["No answer"], "exception": None}])["overall"]
    assert summary["coverage"] == 0
    assert summary["numeric_accuracy_when_answered"] is None


def test_legacy_benchmark_no_longer_counts_refusals_as_correct_numbers():
    result = evaluate_example(generate_family("retail", 42, 12))
    assert result["numeric_evaluation"].startswith("independent Decimal")
    assert len(result["numeric_records"]) == 2
    assert result["numeric_correctness"] == sum(not item["errors"] for item in result["numeric_records"]) / 2
