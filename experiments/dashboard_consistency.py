"""Reproducible valid/contradictory dashboard contract cases, not a performance claim."""
import json
import pandas as pd
from aura import DashboardComponent, DashboardConsistencyEngine, compute_visualization_evidence

if __name__ == "__main__":
    frame = pd.DataFrame({"Sales": [100.0, 200.0], "Region": ["North", "South"]})
    evidence = compute_visualization_evidence(frame, dataset_id="demo", dataset_version_id="v1", metric_column="Sales", dimension="Region")
    evidence["definition"]["term"] = "sales"
    component = DashboardComponent("headline", "KPI", evidence["evidence_id"], "demo", "v1", {"term": "sales", "measure_column": "Sales"}, "sum", {}, "all supplied rows", None, None, "VERIFIED", 300.0)
    valid = DashboardConsistencyEngine().verify([component], [evidence])
    component.displayed_value = 0.0
    invalid = DashboardConsistencyEngine().verify([component], [evidence])
    print(json.dumps({"design": "labeled valid/invalid dashboard contracts; not a benchmark", "valid": valid["status"], "invalid": invalid["status"], "invalid_codes": [x["code"] for x in invalid["issues"]]}, indent=2))
