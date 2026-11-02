"""Deterministic review fingerprints for replay; not authentication tokens."""
from hashlib import sha256
import json


def review_token(query_id, result):
    payload = {"query_id": query_id, "status": result["status"], "plan": result["plan"],
               "definition": result.get("definition"),
               "evidence": [{key: item.get(key) for key in
                             ("dataset_id", "source_columns", "filters", "method", "result",
                              "definition", "semantic_corrections", "result_bindings", "interpretation_status", "scope")}
                            for item in result["evidence"]]}
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
