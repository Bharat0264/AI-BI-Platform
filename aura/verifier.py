"""Deterministic evidence verifier; it never invents analytical support."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from numbers import Number
from typing import Any

from .provenance import EvidenceClaim

SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class VerificationResult:
    status: str
    claims: list[dict[str, Any]]
    unsupported_claim_count: int
    missing_evidence_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceVerifier:
    """Checks claims against the compact, computed AnalyticsEvidence payload."""

    @staticmethod
    def _values(value: Any) -> list[Any]:
        if isinstance(value, dict):
            values = []
            for item in value.values():
                values.extend(EvidenceVerifier._values(item))
            return values
        if isinstance(value, list):
            return [entry for item in value for entry in EvidenceVerifier._values(item)]
        return [value]

    def verify(self, claims: list[EvidenceClaim | dict], evidence: list[dict], requested_columns: list[str] | None = None) -> VerificationResult:
        by_id = {item.get("evidence_id"): item for item in evidence}
        requested_columns = set(requested_columns or [])
        checked: list[dict[str, Any]] = []
        unsupported = missing = 0
        for raw in claims:
            claim = raw if isinstance(raw, EvidenceClaim) else EvidenceClaim(**raw)
            record = by_id.get(claim.evidence_id)
            status = SUPPORTED
            if not record or record.get("dataset_id") != claim.dataset_id:
                status = INSUFFICIENT_EVIDENCE; missing += 1
            elif requested_columns and not requested_columns.issubset(set(record.get("source_columns", []))):
                status = PARTIALLY_SUPPORTED
            elif claim.filters != record.get("filters", {}):
                status = UNSUPPORTED
            elif claim.operation not in str(record.get("method", "")) and claim.operation not in {"sum", "mean", "ranking"}:
                status = PARTIALLY_SUPPORTED
            elif isinstance(claim.expected_value, Number):
                candidates = [x for x in self._values(record.get("result", {})) if isinstance(x, Number)]
                if not any(abs(float(candidate) - float(claim.expected_value)) <= claim.tolerance for candidate in candidates):
                    status = UNSUPPORTED
            claim.supported = status == SUPPORTED
            claim.verification_status = status
            if status in {UNSUPPORTED, PARTIALLY_SUPPORTED}: unsupported += 1
            checked.append(claim.to_dict())
        overall = SUPPORTED if checked and unsupported == 0 and missing == 0 else (INSUFFICIENT_EVIDENCE if missing else UNSUPPORTED)
        return VerificationResult(overall, checked, unsupported, missing)
