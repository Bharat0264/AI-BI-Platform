"""Deterministic research metrics and cautious summary statistics."""
from __future__ import annotations
from collections import defaultdict
from math import sqrt
from statistics import mean, stdev

def classification_metrics(expected: dict[str,str], predicted: dict[str,str]) -> dict:
    labels=sorted(set(expected.values()) | set(predicted.values()))
    correct=sum(predicted.get(k)==v for k,v in expected.items()); per_role={}
    for role in labels:
        tp=sum(expected.get(k)==role and predicted.get(k)==role for k in expected)
        fp=sum(predicted.get(k)==role and expected.get(k)!=role for k in predicted)
        fn=sum(expected.get(k)==role and predicted.get(k)!=role for k in expected)
        p=tp/(tp+fp) if tp+fp else 0.; r=tp/(tp+fn) if tp+fn else 0.; f=2*p*r/(p+r) if p+r else 0.
        per_role[role]={"precision":p,"recall":r,"f1":f,"support":sum(v==role for v in expected.values())}
    macro={metric:sum(entry[metric] for entry in per_role.values())/max(len(per_role),1) for metric in ("precision","recall","f1")}
    return {"accuracy":correct/max(len(expected),1),"macro_precision":macro["precision"],"macro_recall":macro["recall"],"macro_f1":macro["f1"],"per_role":per_role}

def prf(expected: set, predicted: set) -> dict:
    tp=len(expected & predicted); p=tp/len(predicted) if predicted else 0.; r=tp/len(expected) if expected else 0.; f=2*p*r/(p+r) if p+r else 0.
    return {"precision":p,"recall":r,"f1":f}

def answerability_metrics(rows: list[dict]) -> dict:
    expected={i for i,row in enumerate(rows) if row["expected"]=="ANSWERABLE"}; predicted={i for i,row in enumerate(rows) if row["actual"]=="ANSWERABLE"}
    out=prf(expected,predicted); out["accuracy"]=sum(row["expected"]==row["actual"] for row in rows)/max(len(rows),1); return out

def grounding_metrics(claims: list[dict]) -> dict:
    numeric=[c for c in claims if c.get("claim_type")=="numerical"]
    supported=sum(c.get("verification_status")=="SUPPORTED" for c in numeric)
    return {"supported_claim_rate":supported/max(len(numeric),1),"unsupported_numerical_claim_rate":(len(numeric)-supported)/max(len(numeric),1),"evidence_grounding_score":supported/max(len(claims),1)}

def summary(values: list[float]) -> dict:
    count=len(values); average=mean(values) if values else 0.; sd=stdev(values) if count>1 else 0.; ci=1.96*sd/sqrt(count) if count>1 else 0.
    return {"mean":average,"standard_deviation":sd,"ci95_low":average-ci,"ci95_high":average+ci,"sample_count":count}

def group_summaries(rows: list[dict], metric: str, groups: list[str]) -> list[dict]:
    buckets=defaultdict(list)
    for row in rows: buckets[tuple(row.get(key) for key in groups)].append(float(row[metric]))
    return [{**dict(zip(groups,key)),metric:summary(values)} for key,values in sorted(buckets.items())]
