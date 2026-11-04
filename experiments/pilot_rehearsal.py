"""Synthetic-only rehearsal of rejection paths; never creates an evaluation corpus."""
from __future__ import annotations
import json, tempfile
from pathlib import Path
from benchmark.freeze import freeze_readiness
from benchmark.independent import sha256_json

def run():
    with tempfile.TemporaryDirectory() as name:
        root=Path(name); records=[{"Revenue":1}]
        (root/"manifest.json").write_text(json.dumps({"authorship":"synthetic_development","frozen_at":None}))
        (root/"inputs.jsonl").write_text(json.dumps({"case_id":"SYNTHETIC-ONLY","dataset_id":"synthetic","dataset_family":"synthetic","template_family":"synthetic","records":records,"question":"Synthetic rehearsal only","source_sha256":sha256_json(records)})+"\n")
        for filename in ("labels.jsonl","annotators.jsonl","adjudications.jsonl"):
            (root/filename).write_text("")
        (root/"experiment_config.json").write_text("{}")
        return freeze_readiness(root)
if __name__=="__main__": print(json.dumps(run(),indent=2))
