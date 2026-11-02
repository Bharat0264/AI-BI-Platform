"""Read-time freshness over immutable evidence -> answers -> report dependencies."""
from __future__ import annotations

from datetime import datetime, timezone


class LifecycleRepository:
    def _artifact(self, workspace_id, kind, artifact_id):
        collections = {"answer": ("ai_queries", "query_id"), "evidence": ("analytics_evidence", "evidence_id"),
                       "report": ("reports", "report_id")}
        if kind not in collections or not isinstance(artifact_id, str):
            raise ValueError("Unsupported artifact reference.")
        collection, key = collections[kind]
        item = self.db[collection].find_one({"workspace_id": workspace_id, key: artifact_id}, {"_id": 0})
        if not item:
            raise ValueError("Artifact not found in the current workspace.")
        return item

    def artifact_state(self, workspace_id, kind, artifact_id, active_dataset_id=None, _visited=None):
        item = self._artifact(workspace_id, kind, artifact_id)
        visited = set(_visited or ())
        key = (kind, artifact_id)
        reasons = []
        if len(visited) >= 64:
            return {"status": "UNKNOWN", "reasons": [{"code": "DEPENDENCY_DEPTH_LIMIT"}]}
        if key in visited:
            return {"status": "UNKNOWN", "reasons": [{"code": "DEPENDENCY_CYCLE"}]}
        visited.add(key)
        if item.get("lifecycle_version") != 1:
            reasons.append({"code": "LEGACY_UNTRACKED_ARTIFACT"})
        dataset_id = item["dataset_id"]
        if active_dataset_id is not None and dataset_id != active_dataset_id:
            reasons.append({"code": "DIFFERENT_ACTIVE_SNAPSHOT", "recorded_dataset_id": dataset_id,
                            "active_dataset_id": active_dataset_id})
        dataset = self.db.datasets.find_one({"workspace_id": workspace_id, "dataset_id": dataset_id})
        if not dataset:
            reasons.append({"code": "MISSING_DATASET"})
        definition = item.get("definition") or {}
        reference = definition.get("saved_reference")
        if reference:
            if reference.get("workspace_id") != workspace_id or reference.get("dataset_id") != dataset_id:
                reasons.append({"code": "INVALID_DEFINITION_SCOPE"})
            head = self.db.business_definitions.find_one(
                {"workspace_id": workspace_id, "dataset_id": dataset_id, "term": reference.get("term")},
                sort=[("version", -1)])
            if (not head or not head["active"] or head["definition_id"] != reference.get("definition_id")
                    or head["version"] != reference.get("version")):
                reasons.append({"code": "DEFINITION_CHANGED", "reference": reference,
                                "latest_version": head["version"] if head else None})
        if kind == "evidence" and "semantic_corrections" in item and dataset:
            legacy = self.db.settings.find_one({"key": f"aura_schema:{dataset['name']}"})
            current = {**((legacy or {}).get("value") or {}), **self.corrections(dataset_id)}
            before = item["semantic_corrections"]
            changed = [col for col in item.get("source_columns", []) if before.get(col) != current.get(col)]
            if changed:
                reasons.append({"code": "SEMANTIC_CORRECTION_CHANGED", "columns": changed})
        if kind == "answer" and item.get("answerability") == "OK" and not item.get("evidence_ids"):
            reasons.append({"code": "MISSING_EVIDENCE"})
        dependencies = [("evidence", eid) for eid in item.get("dependency_evidence_ids", [])] if kind == "evidence" else []
        if kind in {"answer", "report"}:
            dependencies.extend(("evidence", eid) for eid in item.get("evidence_ids", []))
        if kind == "report":
            dependencies.extend(("answer", qid) for qid in item.get("answer_ids", []))
            dependencies.extend(("report", rid) for rid in item.get("parent_report_ids", []))
        for dependency_kind, dependency_id in dependencies:
            try:
                state = self.artifact_state(workspace_id, dependency_kind, dependency_id,
                                            active_dataset_id, visited)
            except ValueError:
                state = {"status": "UNKNOWN", "reasons": [{"code": "MISSING_OR_FOREIGN_DEPENDENCY"}]}
            if state["status"] != "CURRENT":
                reasons.append({"code": "DEPENDENCY_" + state["status"], "kind": dependency_kind,
                                "id": dependency_id, "reasons": state["reasons"]})
        stale_codes = {"DIFFERENT_ACTIVE_SNAPSHOT", "DEFINITION_CHANGED", "SEMANTIC_CORRECTION_CHANGED", "DEPENDENCY_STALE"}
        status = "STALE" if any(r["code"] in stale_codes for r in reasons) else "UNKNOWN" if reasons else "CURRENT"
        if kind == "evidence" and item.get("interpretation_status") == "CONDITIONAL" and status == "CURRENT":
            status = "UNRESOLVED"
            reasons.append({"code": "UNSELECTED_INTERPRETATION"})
        if (kind == "answer" and item.get("answerability") != "OK"
                and (status == "CURRENT" or all(r["code"] == "DEPENDENCY_UNRESOLVED" for r in reasons))):
            status = "UNRESOLVED"
            reasons.append({"code": "NO_RESOLVED_ANSWER"})
        return {"status": status, "reasons": reasons,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "notice": "Freshness of recorded dependencies, not a guarantee of analytical correctness."}

    def artifact_detail(self, workspace_id, kind, artifact_id, active_dataset_id=None):
        item = self._artifact(workspace_id, kind, artifact_id)
        if kind == "answer":
            item["evidence"] = list(self.db.analytics_evidence.find(
                {"workspace_id": workspace_id, "dataset_id": item["dataset_id"],
                 "evidence_id": {"$in": item.get("evidence_ids", [])}}, {"_id": 0}))
        return {**item, "lifecycle": self.artifact_state(workspace_id, kind, artifact_id, active_dataset_id)}

    def artifact_list(self, workspace_id, kind, active_dataset_id=None, limit=100):
        collection, key = {"answer": ("ai_queries", "query_id"), "report": ("reports", "report_id")}[kind]
        return [self.artifact_detail(workspace_id, kind, item[key], active_dataset_id)
                for item in self.db[collection].find({"workspace_id": workspace_id}, {key: 1})
                    .sort("created_at", -1).limit(limit)]

    def report_evidence(self, workspace_id, dataset_id, limit=10):
        self._definition_scope(workspace_id, dataset_id)
        current, excluded = [], 0
        for item in self.db.analytics_evidence.find({"workspace_id": workspace_id, "dataset_id": dataset_id}, {"_id": 0}).sort("created_at", -1):
            if self.artifact_state(workspace_id, "evidence", item["evidence_id"], dataset_id)["status"] == "CURRENT":
                current.append(item)
                if len(current) == limit:
                    break
            else:
                excluded += 1
        return current, excluded
