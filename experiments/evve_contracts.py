"""Reproducible EVVE contract demonstration; it reports cases, not performance claims."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from aura import VisualizationVerifier, build_visualization_specification, compute_visualization_evidence


def run():
    frame = pd.DataFrame({"Sales": [100.0, 300.0, 50.0], "Region": ["North", "South", "North"]})
    evidence = compute_visualization_evidence(frame, dataset_id="evve-demo", dataset_version_id="v1", metric_column="Sales", dimension="Region")
    valid = build_visualization_specification(evidence)
    invalid = build_visualization_specification(evidence)
    invalid.data_series[0]["y"] = -999.0
    verifier = VisualizationVerifier()
    return {"design": "deterministic valid/invalid contract demonstration; not a benchmark", "valid": verifier.verify(valid, [evidence]), "invalid": verifier.verify(invalid, [evidence])}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
