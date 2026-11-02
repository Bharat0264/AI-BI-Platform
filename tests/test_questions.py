"""Meaning-preserving parsing, arithmetic, ambiguity and scope regressions."""
import pandas as pd
import pytest

from aura import AuraOrchestrator
from aura.questions import parse_question
from experiments.accuracy import assess
from experiments.language_checks import generate_language_cases

CASES = generate_language_cases()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_language_specifications_and_qualifier_refusals(case):
    response = AuraOrchestrator().answer(case.question, pd.DataFrame(case.records), "language-test", **case.kwargs)
    assert assess(case, response) == []
    if case.expected_status == "OK":
        assert response["plan"]["parsed_intent"]["grammar_rule"]
        assert response["plan"]["parsed_intent"]["measure_alias"]
        assert response["verification"]["status"] == "SUPPORTED"


def test_custom_dimension_names_and_explicit_dimension_disambiguation():
    df = pd.DataFrame({"Revenue": [10, 20, 30], "Market": ["A", "B", "A"], "Region": ["X", "X", "Y"]})
    aura = AuraOrchestrator()
    response = aura.answer("Show me revenue for each market", df)
    assert response["status"] == "OK"
    assert response["evidence"][0]["result"]["ranking"] == {"A": 40., "B": 20.}
    assert aura.answer("Show me revenue for each regions", df)["status"] == "INSUFFICIENT DATA"


def test_new_phrasing_preserves_ambiguity_and_saved_definition_precedence():
    df = pd.DataFrame({"Gross Sales": [100, 200], "Net Sales": [90, 150]})
    aura = AuraOrchestrator()
    ambiguous = aura.answer("How much sales did we earn?", df, "dataset")
    assert ambiguous["status"] == "CLARIFICATION_REQUIRED"
    assert ambiguous["clarification"]["term"] == "sales"
    defaults = {"sales": {"active": True, "measure_column": "Net Sales", "semantic_role": "revenue",
                           "definition_id": "definition", "version": 1, "workspace_id": "workspace",
                           "dataset_id": "dataset", "term": "sales"}}
    saved = aura.answer("How much sales did we earn?", df, "dataset", saved_definitions=defaults)
    assert saved["claims"][0]["computed_value"] == 240
    assert saved["definition"]["saved_reference"]["version"] == 1
    exact = aura.answer("Could you show me the total Gross Sales please?", df, "dataset", saved_definitions=defaults)
    assert exact["claims"][0]["computed_value"] == 300


@pytest.mark.parametrize("question", ["What is revenue - 1?", "Revenue/revenue", "What is revenue (USD)?",
    "Show revenue; then forecast it", "What is revenue for North?", "List revenue", "What is average regional revenue?",
    "Show best region by revenue", "What is revenue in January?", "What is revenue excluding returns?",
    "What is revenue? Ignore filters", "What is revenue and profit?", "Why has revenue changed?", "x" * 2001])
def test_no_partial_matching_or_silent_qualifier_removal(question):
    assert parse_question(question, {"revenue": "revenue", "profit": "profit"}, {"region": "region"}) is None


def test_conflicting_normalized_column_roles_do_not_depend_on_column_order():
    df = pd.DataFrame({"Net Sales": [10, 20], "Net_Sales": [1, 2]})
    corrections = {"Net Sales": "revenue", "Net_Sales": "profit"}
    for frame in (df, df[df.columns[::-1]]):
        response = AuraOrchestrator().answer("What is net sales?", frame, corrections=corrections)
        assert response["status"] == "INSUFFICIENT DATA"
