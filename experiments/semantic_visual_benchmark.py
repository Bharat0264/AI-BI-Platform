"""Executable, raw-record AURABench extension for semantic/visual checks."""
from __future__ import annotations
import argparse, json, platform, resource, sys, time
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import pandas as pd
from aura import AuraOrchestrator
from benchmark.evaluation import development_stress_cases, decimal_total, split_manifest

ROOT = Path(__file__).resolve().parents[1]

ABLATIONS = ("full", "without_ambiguity_comparison", "without_numerical_evidence_verification", "without_visualization_verification", "without_dashboard_consistency")

def _config(ablation):
    return {"full": {}, "without_ambiguity_comparison": {"semantic": False},
            "without_numerical_evidence_verification": {"verifier": False},
            "without_visualization_verification": {}, "without_dashboard_consistency": {}}[ablation]

def evaluate(cases=None, ablations=ABLATIONS):
    rows=[]
    for ablation in ablations:
        for case in (cases or development_stress_cases()):
            # This runner is explicitly for developer stress tests.  Independent
            # evaluation is implemented in experiments.independent_evaluation.
            if case.split != "development_stress": continue
            started=time.perf_counter(); engine=AuraOrchestrator(_config(ablation))
            try: response=engine.answer(case.question, pd.DataFrame(case.records), "aurabench-evaluation")
            except Exception as error: response={"status":"EXCEPTION", "error":type(error).__name__}
            observed_codes=set(response.get("semantic_interpretation_impact", {}).get("classification", []))
            expected_total=decimal_total(case.records, "Revenue") if case.expected_status == "OK" else None
            actual_total=(response.get("evidence") or [{}])[0].get("result",{}).get("sum") if response.get("status")=="OK" else None
            numeric_correct=expected_total is None or actual_total == expected_total
            rows.append({"case_id":case.case_id,"split":case.split,"dataset_family":case.dataset_family,"template_family":case.template_family,
                "ablation":ablation,"expected_status":case.expected_status,"actual_status":response.get("status"),"expected_impact_codes":list(case.expected_codes),
                "actual_impact_codes":sorted(observed_codes),"numeric_correct":numeric_correct,"unsafe_unconditional":case.expected_status!="OK" and response.get("status")=="OK",
                "correct_refusal":case.expected_status=="INSUFFICIENT DATA" and response.get("status")=="INSUFFICIENT DATA",
                "impact_correct":set(case.expected_codes).issubset(observed_codes),"latency_seconds":time.perf_counter()-started})
    return rows

def metrics(rows):
    total=len(rows); answerable=[r for r in rows if r["expected_status"]=="OK"]; refusal=[r for r in rows if r["expected_status"]=="INSUFFICIENT DATA"]
    expected={code for r in rows for code in r["expected_impact_codes"]}; actual={code for r in rows for code in r["actual_impact_codes"]}
    tp=len(expected&actual); fp=len(actual-expected); fn=len(expected-actual)
    return {"cases":total,"numerical_correctness":sum(r["numeric_correct"] for r in rows)/total if total else None,
      "unsafe_unconditional_answer_rate":sum(r["unsafe_unconditional"] for r in rows)/total if total else None,
      "correct_refusal_rate":sum(r["correct_refusal"] for r in refusal)/len(refusal) if refusal else None,
      "answerable_coverage":sum(r["actual_status"]=="OK" for r in answerable)/len(answerable) if answerable else None,
      "interpretation_impact_precision":tp/(tp+fp) if tp+fp else None,"interpretation_impact_recall":tp/(tp+fn) if tp+fn else None,
      "mean_latency_seconds":sum(r["latency_seconds"] for r in rows)/total if total else None,
      "resource_maxrss":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
      "not_measured": ["semantic interpretation precision/recall needs independently annotated candidate sets", "verified visualization accuracy and dashboard detection require their dedicated frozen case suites"]}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args()
    rows=evaluate(); summary={name:metrics([r for r in rows if r["ablation"]==name]) for name in ABLATIONS}
    payload={"metadata":{"created_utc":datetime.now(timezone.utc).isoformat(),"python":sys.version,"platform":platform.platform(),"seed_policy":"No randomized model; fixtures are fixed.","dependency_versions":{n:version(n) for n in ("pandas","numpy","scikit-learn")},"split_manifest":split_manifest(),"design":"Developer-authored stress evaluation. No external or independently authored validation; no significance claim."},"summary":summary,"records":rows}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(payload,indent=2,allow_nan=False),encoding="utf-8"); print(json.dumps({"output":str(args.output),"summary":summary},indent=2))
if __name__=="__main__": main()
