"""Claim-level, evidence-grounded provenance for AURA-BI analytics."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4


@dataclass
class EvidenceClaim:
    """A single analytical statement linked to a deterministic evidence record."""

    claim_id: str
    claim_text: str
    claim_type: str
    evidence_id: str
    dataset_id: str
    source_columns: list[str]
    filters: dict[str, Any]
    operation: str
    expected_value: Any
    computed_value: Any
    tolerance: float
    supported: bool = False
    verification_status: str = "PENDING"

    @classmethod
    def numeric(
        cls, *, claim_text: str, evidence: dict, value: float, operation: str, tolerance: float = 1e-6
    ) -> "EvidenceClaim":
        return cls(
            claim_id=str(uuid4()), claim_text=claim_text, claim_type="numerical",
            evidence_id=evidence["evidence_id"], dataset_id=evidence["dataset_id"],
            source_columns=list(evidence.get("source_columns", [])), filters=dict(evidence.get("filters", {})),
            operation=operation, expected_value=value, computed_value=value, tolerance=tolerance,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

