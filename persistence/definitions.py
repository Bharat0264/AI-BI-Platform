"""Append-only, optimistic-concurrency storage for confirmed column definitions."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

MEASURE_TERMS = {"sales": "revenue", "revenue": "revenue", "profit": "profit",
                 "cost": "cost", "costs": "cost", "quantity": "quantity"}


class DefinitionConflict(ValueError):
    """The caller must review a newer version before saving another change."""


class DefinitionRepository:
    def _definition_scope(self, workspace_id, dataset_id, term=None):
        if not self.db.datasets.find_one({"workspace_id": workspace_id, "dataset_id": dataset_id}):
            raise ValueError("Dataset does not belong to the current workspace.")
        scope = {"workspace_id": workspace_id, "dataset_id": dataset_id}
        if term is not None:
            if not isinstance(term, str) or term not in MEASURE_TERMS:
                raise ValueError("Term must be sales, revenue, profit, cost, costs or quantity.")
            scope["term"] = term
        return scope

    def definition_history(self, workspace_id, dataset_id, term):
        scope = self._definition_scope(workspace_id, dataset_id, term)
        return list(self.db.business_definitions.find(scope, {"_id": 0}).sort("version", ASCENDING))

    def definition_defaults(self, workspace_id, dataset_id):
        scope = self._definition_scope(workspace_id, dataset_id)
        latest = {}
        for item in self.db.business_definitions.find(scope, {"_id": 0}).sort("version", DESCENDING):
            latest.setdefault(item["term"], item)
        return {term: item for term, item in latest.items() if item["active"]}

    def save_definition(self, workspace_id, dataset_id, term, measure_column, semantic_role,
                        expected_version, confirmed_by, *, active=True):
        scope = self._definition_scope(workspace_id, dataset_id, term)
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
            raise ValueError("expected_version must be a non-negative integer.")
        if not isinstance(active, bool):
            raise ValueError("active must be boolean.")
        if active and (not isinstance(measure_column, str) or not measure_column
                       or semantic_role != MEASURE_TERMS[term]):
            raise ValueError("The selected column must have the requested business role.")
        if not isinstance(confirmed_by, str) or not confirmed_by.strip():
            raise ValueError("A confirmation actor is required.")
        # Enforce uniqueness even when used without application initialization.
        self.db.business_definitions.create_index(
            [(key, ASCENDING) for key in ("workspace_id", "dataset_id", "term", "version")], unique=True)
        current = self.db.business_definitions.find_one(scope, sort=[("version", DESCENDING)])
        current_version = current["version"] if current else 0
        if current_version != expected_version:
            raise DefinitionConflict("The definition changed. Read its latest version and review before saving.")
        if not active and (not current or not current["active"]):
            raise ValueError("No active definition exists to disable.")
        item = {**scope, "definition_id": current["definition_id"] if current else str(uuid4()),
                "version": current_version + 1, "active": active,
                "measure_column": measure_column if active else current["measure_column"],
                "semantic_role": semantic_role if active else current["semantic_role"],
                "confirmed_by": confirmed_by.strip(),
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
                "scope": "exact dataset snapshot", "kind": "measure column default"}
        try:
            self.db.business_definitions.insert_one(dict(item))
        except DuplicateKeyError as exc:
            raise DefinitionConflict("A concurrent definition update was saved. Reload before retrying.") from exc
        return item
