"""Developer-only measured evidence package; never an independent evaluation."""
from __future__ import annotations
import io,json,os,platform,resource,statistics,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
os.environ.setdefault("MPLCONFIGDIR","/private/tmp/aura-mpl")
os.environ.setdefault("MPLBACKEND","Agg")
import matplotlib.pyplot as plt
from aura import AuraOrchestrator, EvidenceVerifier, EvidenceVerifiedVisualizationEngine, ResearchDashboardPipeline, DashboardComponent, DashboardConsistencyEngine, build_visualization_specification
from benchmark.evaluation import development_stress_cases
sys.path.insert(0,str(ROOT / "app") if "ROOT" in globals() else str(Path(__file__).resolve().parents[1]/"app"))
from report_generator import generate_research_report

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"outputs/paper_evidence"; RAW=ROOT/"benchmark/collection/raw"
def write_json(path,obj): path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,default=str),encoding="utf-8")
def sources():
 retail=pd.read_excel(io.BytesIO(zipfile.ZipFile(RAW/"online-retail.zip").read("Online Retail.xlsx")))
 shoppers=pd.read_csv(io.BytesIO(zipfile.ZipFile(RAW/"online-shoppers.zip").read("online_shoppers_intention.csv")))
 outer=zipfile.ZipFile(RAW/"bank-marketing.zip"); inner=zipfile.ZipFile(io.BytesIO(outer.read("bank.zip")));bank=pd.read_csv(io.BytesIO(inner.read("bank-full.csv")),sep=";")
 return {"Online Retail":retail,"Online Shoppers Purchasing Intention":shoppers,"Bank Marketing":bank}
def timing(name,fn,n=10):
 samples=[]
 for _ in range(n):
  start=time.perf_counter_ns();fn();samples.append((time.perf_counter_ns()-start)/1e6)
 return {"component":name,"repetitions":n,"unit":"ms","mean":statistics.mean(samples),"median":statistics.median(samples),"p95":sorted(samples)[max(0,round(.95*(n-1))-1)],"min":min(samples),"max":max(samples),"samples":samples}
def fig(name,labels,values,title):
 fig_,ax=plt.subplots(figsize=(7,4));ax.bar(labels,values,color="#0f766e");ax.set_title(title);ax.set_ylabel("Count");plt.xticks(rotation=20,ha="right");fig_.tight_layout()
 for suffix in ("png","svg"):fig_.savefig(OUT/"figures"/f"{name}.{suffix}",dpi=300 if suffix=="png" else None)
 plt.close(fig_)
def main():
 for folder in ("datasets","development","deployment","comparisons","figures","tables","provenance"): (OUT/folder).mkdir(parents=True,exist_ok=True)
 data=sources(); summaries=[]
 for name,df in data.items():
  summaries.append({"dataset":name,"rows":len(df),"columns":len(df.columns),"features":list(map(str,df.columns)),"dtypes":{str(k):str(v) for k,v in df.dtypes.items()},"missing_values":{str(k):int(v) for k,v in df.isna().sum().items()},"identity":"official UCI original archive; SHA-256 in benchmark/collection/acquisition_manifest.json","limitations":"Raw schema may lack an analyst-supported monetary field or unambiguous business definition."})
 write_json(OUT/"datasets"/"dataset_summaries.json",summaries);pd.DataFrame([{k:v for k,v in row.items() if k not in {"features","dtypes","missing_values"}} for row in summaries]).to_csv(OUT/"tables"/"dataset_summary.csv",index=False)
 # Use a bounded actual-source-derived developer fixture (not a benchmark corpus).
 retail=data["Online Retail"].head(5000).copy(); retail["Gross Sales"]=pd.to_numeric(retail["Quantity"],errors="coerce")*pd.to_numeric(retail["UnitPrice"],errors="coerce"); retail["Net Sales"]=pd.to_numeric(retail["UnitPrice"],errors="coerce"); retail=retail.rename(columns={"Country":"Category"})[["Gross Sales","Net Sales","Category"]]
 a=AuraOrchestrator(); questions=[("total","What is gross sales?","OK"),("average","What is average gross sales?","OK"),("group","What is gross sales by category?","OK"),("rank","Which category has the highest gross sales?","OK"),("ambiguous","What is sales by category?","CLARIFICATION_REQUIRED"),("causal","Why did sales decline?","INSUFFICIENT DATA")]
 correctness=[];ambiguity=[]
 for cid,q,expected in questions:
  r=a.answer(q,retail,"dev-retail"); claim=(r.get("claims")or[{}])[0]; actual=claim.get("computed_value");definition=r.get("definition",{});oracle=None
  if r["status"]=="OK":
   values=pd.to_numeric(retail[definition["measure_column"]],errors="coerce")
   if r["plan"]["analytical_task"]=="ranking": oracle=float(retail.assign(_v=values).groupby(definition["grouping_column"])["_v"].sum().max())
   elif definition["aggregation"]=="mean":oracle=float(values.mean())
   else:oracle=float(values.sum())
  correctness.append({"case_id":cid,"question":q,"expected_status":expected,"actual_status":r["status"],"expected_value":oracle,"actual_value":actual,"difference":None if oracle is None or actual is None else actual-oracle,"numerical_correct":oracle is not None and abs(actual-oracle)<1e-6,"evidence_status":r.get("verification",{}).get("status"),"failure_reason":None if r["status"]==expected else r["answer"]})
  if r["status"]=="CLARIFICATION_REQUIRED":ambiguity.append({"case_id":cid,"impact":r.get("semantic_interpretation_impact",{}).get("classification",[]),"conditional_charts":r.get("conditional_visualizations",{}).get("status"),"unconditional_publication":False})
 pd.DataFrame(correctness).to_csv(OUT/"tables"/"deterministic_correctness.csv",index=False);write_json(OUT/"development"/"deterministic_correctness.json",correctness);write_json(OUT/"development"/"ambiguity_outcomes.json",ambiguity)
 # EVVE deterministic accepted/rejected outcomes.
 ev=EvidenceVerifiedVisualizationEngine(a.verifier); good=ev.build(retail,dataset_id="dev-retail",dataset_version_id="v1",metric_column="Gross Sales",dimension="Category"); bad=build_visualization_specification(good["evidence"]);bad.data_series[0]["y"]=999
 evve=[{"case":"correct_series","expected":"VERIFIED","actual":good["verification"]["status"]},{"case":"incorrect_series","expected":"INVALID","actual":ev.verifier.verify(bad,[good["evidence"]])["status"]}]
 pd.DataFrame(evve).to_csv(OUT/"tables"/"evve_outcomes.csv",index=False);write_json(OUT/"development"/"evve_outcomes.json",evve)
 # Dashboard verified vs scope/currency conflict using actual computed evidence.
 component=DashboardComponent("kpi","KPI",good["evidence"]["evidence_id"],"dev-retail","v1",{"term":"gross sales","measure_column":"Gross Sales"},"sum",{},"all supplied rows",None,None,"VERIFIED",good["evidence"]["result"]["sum"])
 valid=DashboardConsistencyEngine().verify([component],[good["evidence"]]); other=DashboardComponent("other","KPI",good["evidence"]["evidence_id"],"dev-retail","v1",component.definition,"sum",{"Category":["United Kingdom"]},"Q1","EUR",None,"VERIFIED",good["evidence"]["result"]["sum"],"compare") ; component.directly_comparable_group="compare"; conflict=DashboardConsistencyEngine().verify([component,other],[good["evidence"]])
 dashboard=[{"case":"consistent","expected":"PUBLISH_VERIFIED","actual":valid["status"]},{"case":"scope_currency_conflict","expected":"REJECT","actual":conflict["status"]}];pd.DataFrame(dashboard).to_csv(OUT/"tables"/"dashboard_outcomes.csv",index=False);write_json(OUT/"development"/"dashboard_outcomes.json",dashboard)
 pipe=ResearchDashboardPipeline(a); perf_frame=retail.head(1000)
 publishable=pipe.build(df=perf_frame,dataset_id="perf",dataset_version_id="v1",questions=["What is gross sales by category?"])
 timings=[timing("semantic_interpretation",lambda:a.schema.infer(perf_frame)),timing("deterministic_answer_and_evidence",lambda:a.answer("What is gross sales by category?",perf_frame,"perf")),timing("SIIE",lambda:a.answer("What is sales by category?",perf_frame,"perf")),timing("EVVE",lambda:ev.build(perf_frame,dataset_id="perf",dataset_version_id="v1",metric_column="Gross Sales",dimension="Category")),timing("dashboard_consistency",lambda:DashboardConsistencyEngine().verify([component],[good["evidence"]])),timing("unified_pipeline",lambda:pipe.build(df=perf_frame,dataset_id="perf",dataset_version_id="v1",questions=["What is gross sales by category?"])),timing("research_pdf_generation",lambda:generate_research_report(publishable,pipe.report_manifest(publishable)))]
 pd.DataFrame([{k:v for k,v in t.items() if k!="samples"} for t in timings]).to_csv(OUT/"tables"/"component_timings.csv",index=False);write_json(OUT/"development"/"component_timings.json",timings)
 # Figures only for measured developer outcomes; no unsupported baseline/ablation figures.
 fig("numerical_correctness",["correct","incorrect"],[sum(x["numerical_correct"] for x in correctness),sum(not x["numerical_correct"] and x["expected_value"] is not None for x in correctness)],"Developer deterministic numerical correctness")
 fig("ambiguity_outcomes",["clarification","conditional charts"],[len(ambiguity),sum(x["conditional_charts"]=="AMBIGUOUS" for x in ambiguity)],"Developer ambiguity outcomes")
 fig("evve_outcomes",[x["actual"] for x in evve],[1,1],"EVVE deterministic fixtures")
 fig("dashboard_outcomes",[x["actual"] for x in dashboard],[1,1],"Dashboard consistency fixtures")
 fig("component_latency",[t["component"] for t in timings],[t["median"] for t in timings],"Developer component median latency (ms)")
 write_json(OUT/"comparisons"/"missing_evidence.json",{"independent_baseline_comparison":"NOT_RUN: no frozen external human corpus","ablations":"NOT_PLOTTED: developer stress fixtures are not independent evidence","live_deployment_performance":"NOT_RUN: no verified deployment"})
 meta={"classification":"DEVELOPER_ONLY_MEASURED_OUTPUTS","created_at":datetime.now(timezone.utc).isoformat(),"python":sys.version,"platform":platform.platform(),"git_revision":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"working_tree":"dirty research branch; revision is base commit only","maxrss":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"timing_method":"perf_counter_ns; 10 sequential runs on a 1,000-row derived development fixture; warm/cold not separated","limitations":"No human labels, frozen independent corpus, deployment measurements, baseline claims, or scalability inference."};write_json(OUT/"provenance"/"experiment_metadata.json",meta)
if __name__=="__main__":main()
