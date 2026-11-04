"""Matched, executable baseline adapters for the frozen synthetic held-out split.

B5 deliberately returns NOT_RUN without an explicitly enabled provider; it is
never substituted with a deterministic response.
"""
from __future__ import annotations
from copy import deepcopy
import os, time
import pandas as pd
from aura import AuraOrchestrator
from benchmark.evaluation import decimal_total

BASELINES = ("B0_MANUAL", "B1_FIRST_CANDIDATE", "B2_CLARIFICATION_ONLY", "B3_NUMERIC_ONLY", "B4_FULL", "B5_LLM_CHART_PLANNING")

def provider_available():
    return bool(os.getenv("GEMINI_API_KEY")) and os.getenv("AURA_ENABLE_LLM", "false").lower() == "true"

def _policy(response, name):
    result=deepcopy(response)
    if result.get("status") != "CLARIFICATION_REQUIRED": return result
    if name == "B1_FIRST_CANDIDATE" and result.get("alternatives"):
        first=result["alternatives"][0]; result["status"]=first["status"]
        result["evidence"]=[e for e in result["evidence"] if e["evidence_id"] in first["evidence_ids"]]
    elif name == "B2_CLARIFICATION_ONLY":
        result["evidence"]=[]; result["alternatives"]=[]
    return result

def execute(case, baseline):
    """Run one baseline without reading expected labels or answers."""
    started=time.perf_counter(); frame=pd.DataFrame(case.records)
    if baseline == "B5_LLM_CHART_PLANNING" and not provider_available():
        return {"status":"NOT_RUN", "reason":"provider credentials/configuration unavailable", "latency_seconds":time.perf_counter()-started, "cost":None}
    if baseline == "B0_MANUAL":
        # Fixed schema convention: only literal Revenue total, no ambiguity detection.
        if "Revenue" in frame:
            total=decimal_total(case.records, "Revenue")
            response={"status":"OK" if total is not None else "INSUFFICIENT DATA", "evidence":[], "manual_value":total}
        else: response={"status":"INSUFFICIENT DATA", "evidence":[]}
    else:
        config={"B3_NUMERIC_ONLY": {"verifier":True}, "B4_FULL": {}}.get(baseline,{})
        response=AuraOrchestrator(config).answer(case.question, frame, "baseline-evaluation")
        response=_policy(response, baseline)
    return {"status":response.get("status"), "response":response, "latency_seconds":time.perf_counter()-started,
            "cost":0.0 if baseline != "B5_LLM_CHART_PLANNING" else None}
