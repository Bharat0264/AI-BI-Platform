"""Fail-closed gate for a human-authored external benchmark package."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from benchmark.quality_control import validate_package

def freeze_readiness(package: str | Path) -> dict:
    root=Path(package)
    required=["manifest.json","inputs.jsonl","labels.jsonl","annotators.jsonl","adjudications.jsonl","experiment_config.json"]
    missing=[name for name in required if not (root/name).is_file()]
    if missing: return {"status":"NOT_READY","reason":"missing required freeze files","missing":missing}
    manifest=json.loads((root/"manifest.json").read_text())
    if manifest.get("authorship")!="external_human" or not manifest.get("frozen_at"):
        return {"status":"NOT_READY","reason":"human authorship and human-set frozen timestamp are required"}
    report=validate_package(root)
    if report["status"]!="VALID": return {"status":"NOT_READY","reason":"quality controls failed","quality":report}
    return {"status":"READY_FOR_MANUAL_FREEZE","quality":report,"notice":"This gate never writes authorship or timestamps; a human study owner must perform the immutable storage freeze."}

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("package");args=parser.parse_args();print(json.dumps(freeze_readiness(args.package),indent=2))
