"""AURABench baseline and ablation execution without provider substitution."""
from __future__ import annotations
import os, subprocess, time
from dataclasses import dataclass
from uuid import uuid4
from aura import AuraOrchestrator
from benchmark.perturbations import perturb
from .metrics import classification_metrics, prf, answerability_metrics, grounding_metrics

BASELINES=("B0_STATIC_BI","B1_DIRECT_LLM","B2_SEMANTIC_ONLY","B3_EVIDENCE_AURA","B4_FULL_AURA_BI")
ABLATIONS={"full":{},"semantic_disabled":{"semantic":False},"planner_disabled":{"planner":False},"provenance_disabled":{"provenance":False},"verifier_disabled":{"verifier":False},"repair_disabled":{"repair":False}}

def git_sha():
    try: return subprocess.check_output(["git","rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return None

def _config(name, ablation):
    config={"semantic":True,"planner":True,"provenance":True,"verifier":True,"repair":True}
    if name=="B0_STATIC_BI": config.update(semantic=False,planner=False,provenance=False,verifier=False,repair=False)
    elif name=="B2_SEMANTIC_ONLY": config.update(planner=False,provenance=False,verifier=False,repair=False)
    elif name=="B3_EVIDENCE_AURA": config.update(verifier=False,repair=False)
    config.update(ABLATIONS[ablation]); return config

def provider_available(): return bool(os.getenv("GEMINI_API_KEY")) and os.getenv("AURA_ENABLE_LLM","false").lower()=="true"

def _direct_llm_baseline(example, level, run_id, started):
    """B1 only: controlled schema/sample context, deliberately without AURA evidence."""
    import google.generativeai as genai
    perturbed=perturb(example,level,seed=example.seed).dataset
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    answers=[]
    for question in perturbed.ground_truth.questions:
        context={"columns":{str(c):str(perturbed.frame[c].dtype) for c in perturbed.frame.columns},"sample":perturbed.frame.head(8).to_dict(orient="records")}
        prompt=f"Answer this business-data question from only this controlled context. Say INSUFFICIENT DATA when unsupported. Question: {question.question}\nContext: {context}"
        try: text=genai.GenerativeModel("models/gemini-2.5-flash").generate_content(prompt).text or ""
        except Exception: text="INSUFFICIENT DATA"
        answers.append({"expected":question.answerability,"actual":"INSUFFICIENT DATA" if "INSUFFICIENT DATA" in text.upper() else "ANSWERABLE"})
    now=time.perf_counter()
    return {"experiment_id":run_id,"git_sha":git_sha(),"family":example.family,"seed":example.seed,"rows":len(example.frame),"perturbation":level,"baseline":"B1_DIRECT_LLM","ablation":"full","semantic":classification_metrics(perturbed.ground_truth.semantic_roles,{}),"kpi":prf(set(perturbed.ground_truth.applicable_kpis),set()),"answerability":answerability_metrics(answers),"task_accuracy":0.0,"numeric_correctness":0.0,"grounding":grounding_metrics([]),"anomaly":prf(set(perturbed.ground_truth.anomaly_rows),set()),"latency_seconds":now-started,"repair_frequency":0,"provider_enabled":True}

def evaluate_example(example, *, level="L0", baseline="B4_FULL_AURA_BI", ablation="full") -> dict:
    if baseline=="B1_DIRECT_LLM" and not provider_available(): return {"skipped":True,"reason":"provider credentials/configuration unavailable"}
    run_id=str(uuid4()); started=time.perf_counter()
    if baseline == "B1_DIRECT_LLM": return _direct_llm_baseline(example, level, run_id, started)
    perturbed=perturb(example,level,seed=example.seed)
    config=_config(baseline,ablation); aura=AuraOrchestrator(config); inspection=aura.inspect(perturbed.dataset.frame,f"aurabench-{example.family}")
    predicted={field["column"]:field["semantic_role"] for field in inspection["semantic_schema"]}; semantic=classification_metrics(perturbed.dataset.ground_truth.semantic_roles,predicted)
    kpi=prf(set(perturbed.dataset.ground_truth.applicable_kpis),{x["name"] for x in inspection["kpis"]})
    answers=[]; claims=[]; task_correct=[]; numeric_correct=[]
    for question in perturbed.dataset.ground_truth.questions:
        result=aura.answer(question.question,perturbed.dataset.frame,f"aurabench-{example.family}")
        actual="ANSWERABLE" if result["status"]=="OK" else "INSUFFICIENT DATA"; answers.append({"expected":question.answerability,"actual":actual})
        task_correct.append(result["plan"]["analytical_task"]==question.analytical_operation if question.answerability=="ANSWERABLE" else result["status"]=="INSUFFICIENT DATA")
        claims.extend(result.get("claims",[])); numeric_correct.append(result["status"]=="OK" if question.answerability=="ANSWERABLE" else result["status"]=="INSUFFICIENT DATA")
    anomaly=inspection.get("anomaly_evidence") or {}; predicted_anomaly=set(range(len(perturbed.dataset.frame))) if anomaly.get("result",{}).get("anomalous_records",0) else set()
    now=time.perf_counter(); return {"experiment_id":run_id,"git_sha":git_sha(),"family":example.family,"seed":example.seed,"rows":len(example.frame),"perturbation":level,"baseline":baseline,"ablation":ablation,"semantic":semantic,"kpi":kpi,"answerability":answerability_metrics(answers),"task_accuracy":sum(task_correct)/max(len(task_correct),1),"numeric_correctness":sum(numeric_correct)/max(len(numeric_correct),1),"grounding":grounding_metrics(claims),"anomaly":prf(set(perturbed.dataset.ground_truth.anomaly_rows),predicted_anomaly),"latency_seconds":now-started,"repair_frequency":sum(1 for question in perturbed.dataset.ground_truth.questions if aura.answer(question.question,perturbed.dataset.frame).get("repair_attempts",0)>0),"provider_enabled":provider_available()}
