from benchmark.evaluation import development_stress_cases
from experiments.fair_baselines import BASELINES, execute

def test_baselines_are_executable_without_expected_labels():
    case=next(c for c in development_stress_cases() if c.expected_status=="CLARIFICATION_REQUIRED")
    rows={name:execute(case,name) for name in BASELINES}
    assert rows["B1_FIRST_CANDIDATE"]["status"] == "OK"
    assert rows["B2_CLARIFICATION_ONLY"]["status"] == "CLARIFICATION_REQUIRED"
    assert rows["B4_FULL"]["status"] == "CLARIFICATION_REQUIRED"
    assert rows["B5_LLM_CHART_PLANNING"]["status"] == "NOT_RUN"
