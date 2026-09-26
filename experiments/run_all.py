"""Run AURABench smoke, small, or full reproducible research experiments."""
from __future__ import annotations
import argparse, csv, json, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from benchmark.generate import FAMILIES, generate_family
from benchmark.perturbations import LEVELS
from experiments.framework import ABLATIONS, BASELINES, evaluate_example, git_sha
from experiments.metrics import group_summaries

DEFAULT_SEEDS=(42,123,456,789,2026)

def _write_csv(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows: path.write_text(""); return
    keys=sorted({key for row in rows for key in row})
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=keys); writer.writeheader(); writer.writerows(rows)

def _flat(record):
    base={key:value for key,value in record.items() if key not in {"semantic","kpi","answerability","grounding","anomaly"}}
    return {**base,**{f"semantic_{k}":v for k,v in record["semantic"].items() if k!="per_role"},**{f"kpi_{k}":v for k,v in record["kpi"].items()},**{f"answerability_{k}":v for k,v in record["answerability"].items()},**{f"grounding_{k}":v for k,v in record["grounding"].items()},**{f"anomaly_{k}":v for k,v in record["anomaly"].items()}}

def _figures(records, target):
    if not records: return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    target.mkdir(parents=True,exist_ok=True)
    for metric,name,label in (("semantic_macro_f1","semantic_f1_by_system.png","Semantic macro-F1"),("grounding_supported_claim_rate","supported_claim_rate_by_baseline.png","Supported Claim Rate"),("grounding_unsupported_numerical_claim_rate","unsupported_numerical_claim_rate_by_baseline.png","Unsupported Numerical Claim Rate")):
        grouped={}
        for row in records: grouped.setdefault(row["baseline"],[]).append(row[metric])
        names=list(grouped); values=[sum(grouped[n])/len(grouped[n]) for n in names]
        fig,ax=plt.subplots(figsize=(8,4.5)); ax.bar(names,values,color="#3267a8"); ax.set_ylabel(label); ax.set_ylim(0,1); ax.set_title(label+" by system"); plt.xticks(rotation=20,ha="right"); fig.tight_layout(); fig.savefig(target/name,dpi=300); plt.close(fig)
    levels=sorted({row["perturbation"] for row in records})
    fig,ax=plt.subplots(figsize=(8,4.5))
    for baseline in sorted({row["baseline"] for row in records}):
        values=[sum(r["semantic_macro_f1"] for r in records if r["baseline"]==baseline and r["perturbation"]==level)/max(1,sum(r["baseline"]==baseline and r["perturbation"]==level for r in records)) for level in levels]
        ax.plot(levels,values,marker="o",label=baseline)
    ax.set_ylim(0,1); ax.set_ylabel("Semantic macro-F1"); ax.set_title("Semantic F1 vs schema perturbation"); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(target/"semantic_f1_vs_perturbation.png",dpi=300); plt.close(fig)
    for group,metric,name,title in (("ablation","semantic_macro_f1","ablation_comparison.png","Ablation comparison"),("family","semantic_macro_f1","domain_wise_performance.png","Domain-wise semantic performance")):
        labels=sorted({row[group] for row in records}); values=[sum(r[metric] for r in records if r[group]==label)/max(1,sum(r[group]==label for r in records)) for label in labels]
        fig,ax=plt.subplots(figsize=(8,4.5)); ax.bar(labels,values,color="#5a8f60"); ax.set_ylim(0,1); ax.set_ylabel("Semantic macro-F1"); ax.set_title(title); plt.xticks(rotation=25,ha="right"); fig.tight_layout(); fig.savefig(target/name,dpi=300); plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4.5)); ax.scatter([r["latency_seconds"] for r in records],[r["numeric_correctness"] for r in records],alpha=.65,color="#a64d79"); ax.set_xlabel("Latency (seconds)"); ax.set_ylabel("Numeric correctness"); ax.set_ylim(0,1); ax.set_title("Accuracy vs latency"); fig.tight_layout(); fig.savefig(target/"accuracy_vs_latency.png",dpi=300); plt.close(fig)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--mode",choices=("smoke","small","full"),default="smoke"); parser.add_argument("--seed",type=int,default=42); parser.add_argument("--rows",type=int,default=80); args=parser.parse_args()
    if args.mode=="smoke": families=["retail"]; seeds=[args.seed]; levels=["L0"]; baselines=["B4_FULL_AURA_BI"]; ablations=["full"]
    elif args.mode=="small": families=list(FAMILIES); seeds=[args.seed]; levels=list(LEVELS); baselines=["B0_STATIC_BI","B2_SEMANTIC_ONLY","B3_EVIDENCE_AURA","B4_FULL_AURA_BI"]; ablations=["full"]
    else: families=list(FAMILIES); seeds=list(DEFAULT_SEEDS); levels=list(LEVELS); baselines=list(BASELINES); ablations=list(ABLATIONS)
    raw=[]; skipped=[]
    for family in families:
        for seed in seeds:
            example=generate_family(family,seed,args.rows)
            for level in levels:
                for baseline in baselines:
                    for ablation in ablations:
                        result=evaluate_example(example,level=level,baseline=baseline,ablation=ablation)
                        if result.get("skipped"): skipped.append({"family":family,"seed":seed,"level":level,"baseline":baseline,"ablation":ablation,**result}); continue
                        raw.append(result)
    output=ROOT/"outputs"/"experiments"; raw_dir=output/"raw"; table_dir=output/"tables"; figure_dir=output/"figures"; raw_dir.mkdir(parents=True,exist_ok=True)
    run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (raw_dir/f"{run_id}.json").write_text(json.dumps({"experiment_id":run_id,"timestamp":datetime.now(timezone.utc).isoformat(),"git_sha":git_sha(),"mode":args.mode,"seeds":seeds,"rows":args.rows,"records":raw,"skipped":skipped},indent=2),encoding="utf-8")
    flat=[_flat(row) for row in raw]; keys={"family","seed","perturbation","baseline","ablation"}
    _write_csv(table_dir/"semantic_results.csv",[{k:v for k,v in row.items() if k.startswith("semantic_") or k in keys} for row in flat]); _write_csv(table_dir/"kpi_results.csv",[{k:v for k,v in row.items() if k.startswith("kpi_") or k in keys} for row in flat]); _write_csv(table_dir/"answerability_results.csv",[{k:v for k,v in row.items() if k.startswith("answerability_") or k in keys} for row in flat]); _write_csv(table_dir/"grounding_results.csv",[{k:v for k,v in row.items() if k.startswith("grounding_") or k in keys} for row in flat]); _write_csv(table_dir/"robustness_results.csv",flat); _write_csv(table_dir/"ablation_results.csv",flat); _write_csv(table_dir/"latency_results.csv",[{k:row.get(k) for k in (*keys,"latency_seconds","repair_frequency")} for row in flat])
    sprs={baseline:sum(row["semantic_macro_f1"] for row in flat if row["baseline"]==baseline)/max(1,sum(row["baseline"]==baseline for row in flat)) for baseline in sorted({row["baseline"] for row in flat})}
    summary={"experiment_id":run_id,"mode":args.mode,"records":len(raw),"skipped":len(skipped),"semantic_macro_f1":group_summaries(flat,"semantic_macro_f1",["baseline","perturbation"]),"schema_perturbation_robustness_score":sprs,"generated_from_actual_computation":True}; (table_dir/"experiment_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8"); _figures(flat,figure_dir); print(json.dumps(summary))

if __name__=="__main__": main()
