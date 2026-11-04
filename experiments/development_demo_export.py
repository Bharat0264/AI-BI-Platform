"""Create developer-only, reproducible AURA-BI demonstration artifacts.

Source archives are read unchanged. Derived views exist solely to exercise the
supported grammar and are never independent evaluation data.
"""
from __future__ import annotations
import csv, io, json, resource, time, zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
import pandas as pd
from aura import AuraOrchestrator, ResearchDashboardPipeline, DashboardConsistencyEngine
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from report_generator import generate_research_report

ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/"benchmark/collection/raw"; OUT=ROOT/"outputs/paper_evidence/development"
def decimal_sum(values):
 total=Decimal("0")
 for value in values:
  try: candidate=Decimal(str(value))
  except (InvalidOperation,ValueError): continue
  if candidate.is_finite(): total+=candidate
 return float(total)
def sources():
 retail=pd.read_excel(io.BytesIO(zipfile.ZipFile(RAW/"online-retail.zip").read("Online Retail.xlsx")))
 shoppers=pd.read_csv(io.BytesIO(zipfile.ZipFile(RAW/"online-shoppers.zip").read("online_shoppers_intention.csv")))
 outer=zipfile.ZipFile(RAW/"bank-marketing.zip"); inner=zipfile.ZipFile(io.BytesIO(outer.read("bank.zip")))
 bank=pd.read_csv(io.BytesIO(inner.read("bank-full.csv")),sep=";")
 return retail,shoppers,bank
def run():
 retail,shoppers,bank=sources(); analyst=AuraOrchestrator(); pipeline=ResearchDashboardPipeline(analyst); records=[]
 # Documented derived developer views; original frames above are never mutated.
 retail_view=retail.assign(**{"Gross Sales":pd.to_numeric(retail["Quantity"],errors="coerce")*pd.to_numeric(retail["UnitPrice"],errors="coerce"),"Net Sales":pd.to_numeric(retail["UnitPrice"],errors="coerce")})[["Gross Sales","Net Sales","Country"]].rename(columns={"Country":"Category"})
 shopper_view=shoppers.rename(columns={"Revenue":"Purchase Outcome","PageValues":"Revenue"})[["Revenue","Region","VisitorType"]]
 bank_view=bank.assign(Revenue=pd.to_numeric(bank["balance"],errors="coerce"))[["Revenue","job"]].rename(columns={"job":"Category"})
 cases=[
 ("retail-total","Online Retail derived gross/net view",retail_view,"What is gross sales?",{},"OK"),
 ("retail-average","Online Retail derived gross/net view",retail_view,"What is average gross sales?",{},"OK"),
 ("retail-group","Online Retail derived gross/net view",retail_view,"What is gross sales by category?",{},"OK"),
 ("retail-ranking","Online Retail derived gross/net view",retail_view,"Which category has the highest gross sales?",{},"OK"),
 ("retail-ambiguous","Online Retail derived gross/net view",retail_view,"What is sales by category?",{},"CLARIFICATION_REQUIRED"),
 ("retail-ranking-sensitive","Online Retail derived gross/net view",retail_view,"Which category has the highest sales?",{},"CLARIFICATION_REQUIRED"),
 ("retail-causal","Online Retail original",retail,"Why did sales decline?",{},"INSUFFICIENT DATA"),
 ("shoppers-boolean-refusal","Online Shoppers original",shoppers,"What is revenue?",{},"INSUFFICIENT DATA"),
 ("shoppers-total","Online Shoppers derived PageValues view",shopper_view,"What is revenue?",{},"OK"),
 ("shoppers-group","Online Shoppers derived PageValues view",shopper_view,"What is revenue by region?",{},"OK"),
 ("shoppers-ranking","Online Shoppers derived PageValues view",shopper_view,"Which region has the highest revenue?",{},"OK"),
 ("bank-original-refusal","Bank Marketing original",bank,"What is revenue?",{},"INSUFFICIENT DATA"),
 ("bank-total","Bank Marketing derived balance view",bank_view,"What is revenue?",{},"OK"),
 ("bank-average","Bank Marketing derived balance view",bank_view,"What is average revenue?",{},"OK"),
 ("bank-group","Bank Marketing derived balance view",bank_view,"What is revenue by category?",{},"OK"),
 ]
 for case_id,dataset,frame,question,kwargs,expected in cases:
  start=time.perf_counter(); response=analyst.answer(question,frame,case_id,**kwargs); elapsed=time.perf_counter()-start
  claim=(response.get("claims") or [{}])[0]; definition=response.get("definition",{}); column=definition.get("measure_column")
  oracle=None
  if response["status"]=="OK" and column:
   numeric=pd.to_numeric(frame[column],errors="coerce")
   if definition.get("grouping_column") and response["plan"]["analytical_task"]=="ranking":
    grouped=frame.assign(_v=numeric).groupby(definition["grouping_column"])["_v"].sum() if definition.get("aggregation")=="sum" else frame.assign(_v=numeric).groupby(definition["grouping_column"])["_v"].mean()
    oracle=float(grouped.max())
   elif definition.get("aggregation")=="mean": oracle=float(numeric.mean())
   else: oracle=decimal_sum(frame[column])
  actual=claim.get("computed_value"); passed=response["status"]==expected and (oracle is None or abs(actual-oracle)<1e-6)
  records.append({"classification":"DEVELOPMENT_DEMONSTRATION_NOT_INDEPENDENT","case_id":case_id,"dataset":dataset,"question":question,"expected_behavior":expected,"actual_status":response["status"],"numerical_oracle":oracle,"actual_value":actual,"evidence_status":response.get("verification",{}).get("status"),"siie_classification":response.get("semantic_interpretation_impact",{}).get("classification"),"chart_verification":response.get("conditional_visualizations",{}).get("status"),"publication_decision":None,"latency_seconds":elapsed,"pass":passed,"explanation":response["answer"]})
 # Verified and blocked publication decisions from the unified workflow.
 verified=pipeline.build(df=shopper_view,dataset_id="dev-shoppers",dataset_version_id="v1",questions=["What is revenue by region?"])
 manifest=pipeline.report_manifest(verified); pdf,sidecar=generate_research_report(verified,manifest)
 blocked=pipeline.build(df=retail_view,dataset_id="dev-retail",dataset_version_id="v1",questions=["What is sales by category?"])
 records.append({"classification":"DEVELOPMENT_DEMONSTRATION_NOT_INDEPENDENT","case_id":"verified-publication","dataset":"Online Shoppers derived PageValues view","question":"What is revenue by region?","expected_behavior":"PUBLISH_VERIFIED","actual_status":"OK","numerical_oracle":None,"actual_value":None,"evidence_status":"SUPPORTED","siie_classification":None,"chart_verification":"VERIFIED","publication_decision":verified["publication_decision"],"latency_seconds":None,"pass":verified["publication_decision"]=="PUBLISH_VERIFIED","explanation":f"PDF {pdf}; manifest {sidecar}"})
 records.append({"classification":"DEVELOPMENT_DEMONSTRATION_NOT_INDEPENDENT","case_id":"blocked-publication","dataset":"Online Retail derived gross/net view","question":"What is sales by category?","expected_behavior":"CLARIFICATION_REQUIRED","actual_status":"CLARIFICATION_REQUIRED","numerical_oracle":None,"actual_value":None,"evidence_status":"CONDITIONAL","siie_classification":blocked["items"][0]["answer"].get("semantic_interpretation_impact",{}).get("classification"),"chart_verification":"AMBIGUOUS","publication_decision":blocked["publication_decision"],"latency_seconds":None,"pass":blocked["publication_decision"]=="CLARIFICATION_REQUIRED","explanation":"Conditional interpretations excluded from report publication."})
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"development_demonstrations.json").write_text(json.dumps({"classification":"DEVELOPMENT_DEMONSTRATIONS_ONLY","records":records,"maxrss":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2,default=str),encoding="utf-8")
 pd.DataFrame(records).to_csv(OUT/"development_demonstrations.csv",index=False)
 return records
if __name__=="__main__": print(json.dumps({"cases":len(run())},indent=2))
