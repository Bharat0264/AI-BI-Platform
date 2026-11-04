"""Developer-only engineering timing for the unified report contract."""
from __future__ import annotations
import json, resource, time
import pandas as pd
from aura import AuraOrchestrator, ResearchDashboardPipeline
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from report_generator import generate_research_report

def run():
    frame=pd.DataFrame({"Revenue":[100,200,300],"Region":["North","South","North"]})
    pipeline=ResearchDashboardPipeline(AuraOrchestrator()); start=time.perf_counter()
    contract=pipeline.build(df=frame,dataset_id="developer-measure",dataset_version_id="v1",questions=["What is revenue by region?"])
    pipeline_seconds=time.perf_counter()-start
    start=time.perf_counter(); manifest=pipeline.report_manifest(contract); manifest_seconds=time.perf_counter()-start
    start=time.perf_counter(); pdf, sidecar=generate_research_report(contract,manifest); report_seconds=time.perf_counter()-start
    return {"classification":"DEVELOPER_ONLY_ENGINEERING_SMOKE","pipeline_seconds":pipeline_seconds,"manifest_seconds":manifest_seconds,"report_generation_seconds":report_seconds,"maxrss":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"publication_decision":contract["publication_decision"],"pdf":pdf,"manifest":sidecar}
if __name__=="__main__": print(json.dumps(run(),indent=2))
