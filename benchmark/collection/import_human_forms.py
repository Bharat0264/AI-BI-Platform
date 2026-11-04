"""Stage genuine submitted JSONL forms without fabricating authorship or freezing."""
from __future__ import annotations
import argparse,json,shutil
from pathlib import Path

def rows(path): return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
def main():
 p=argparse.ArgumentParser();p.add_argument("--inputs",required=True);p.add_argument("--annotator-a",required=True);p.add_argument("--annotator-b",required=True);p.add_argument("--adjudications",required=True);p.add_argument("--experiment-config",required=True);p.add_argument("--output",required=True);a=p.parse_args()
 out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
 inputs,aa,bb,ad=rows(a.inputs),rows(a.annotator_a),rows(a.annotator_b),rows(a.adjudications)
 if not inputs or not aa or not bb or not ad: raise SystemExit("All supplied files must contain genuine submitted records.")
 if {r.get("annotator_id") for r in aa}&{r.get("annotator_id") for r in bb}: raise SystemExit("Annotators A and B must use distinct pseudonymous IDs.")
 for name,data in (("inputs.jsonl",inputs),("annotators.jsonl",aa+bb),("adjudications.jsonl",ad)):
  (out/name).write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in data),encoding="utf-8")
 labels=[]
 for decision in ad:
  final=decision.get("decision")
  if not isinstance(final,dict): raise SystemExit("Each adjudication needs a final decision object.")
  labels.append({"case_id":decision["case_id"],**final,"adjudication_id":decision["adjudication_id"]})
 (out/"labels.jsonl").write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in labels),encoding="utf-8")
 shutil.copyfile(a.experiment_config,out/"experiment_config.json")
 # Explicitly staged only. A study owner must review and write final manifest fields.
 (out/"manifest.json").write_text(json.dumps({"status":"STAGED_PENDING_HUMAN_REVIEW","authorship":None,"frozen_at":None,"warning":"Importer never asserts external_human authorship or freezes a corpus."},indent=2),encoding="utf-8")
 print(out)
if __name__=="__main__":main()
