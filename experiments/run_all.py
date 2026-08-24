"""Reproducible smoke experiment runner; emits measured results only."""
import argparse, json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from benchmark.generate import retail
from aura import AuraOrchestrator

def main():
    p=argparse.ArgumentParser(); p.add_argument("--seed",type=int,default=42); args=p.parse_args()
    df=retail(args.seed); aura=AuraOrchestrator(); inspection=aura.inspect(df,"aurabench-retail")
    roles={x["column"]:x["semantic_role"] for x in inspection["semantic_schema"]}
    expected={"purchase_date":"date/time","gross_merchandise_value":"revenue","net_margin":"profit","market":"region","product_line":"product"}
    accuracy=sum(roles.get(k)==v for k,v in expected.items())/len(expected)
    out={"seed":args.seed,"status":"smoke","semantic_role_accuracy":accuracy,"dataset_rows":len(df),"note":"Synthetic smoke measurement; not a research claim."}
    target=Path("outputs/experiments"); target.mkdir(parents=True,exist_ok=True); (target/"smoke_results.json").write_text(json.dumps(out,indent=2)); print(json.dumps(out))
if __name__=="__main__": main()
