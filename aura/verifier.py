"""Verify exact numerical result bindings, never coincidental payload matches."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
from numbers import Real
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
    @staticmethod
    def _finite(value):
        return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)

    def verify(self, claims, evidence, requested_columns=None):
        by_id = {}
        duplicate_ids = set()
        for item in evidence:
            key = item.get("evidence_id")
            if key in by_id:
                duplicate_ids.add(key)
            by_id[key] = item
        checked = []
        unsupported = missing = 0
        for raw in claims:
            claim = replace(raw) if isinstance(raw, EvidenceClaim) else EvidenceClaim(**raw)
            record = by_id.get(claim.evidence_id)
            status = UNSUPPORTED
            actual = None
            if not record or record.get("dataset_id") != claim.dataset_id:
                status = INSUFFICIENT_EVIDENCE
                missing += 1
            elif claim.evidence_id not in duplicate_ids:
                result = record.get("result", {})
                path = claim.result_path
                valid_path = path == [claim.operation] and claim.operation in {"sum", "mean", "count"}
                if claim.operation == "ranking":
                    valid_path = path == ["requested_result", "value"]
                comparison_paths = {"period_current": ["current"], "period_baseline": ["baseline"],
                                    "difference": ["difference"], "percent_change": ["percent_change"]}
                if claim.operation in comparison_paths:
                    valid_path = (record.get("analysis_type") == "period comparison"
                                  and path == comparison_paths[claim.operation])
                actual = result
                try:
                    if not path or not all(isinstance(key, str) for key in path):
                        raise KeyError("Missing result binding")
                    for key in path:
                        actual = actual[key]
                except (KeyError, TypeError, IndexError):
                    actual = None
                binding = record.get("result_bindings", {}).get(claim.operation)
                # Legacy records must name an exact operation, not a substring.
                legacy_operation = claim.operation in str(record.get("method", "")).split()
                metadata_valid = (
                    set(claim.source_columns) == set(record.get("source_columns", []))
                    and bool(claim.source_columns)
                    and set(requested_columns or []).issubset(claim.source_columns)
                    and claim.filters == record.get("filters", {})
                    and (binding == path or (binding is None and legacy_operation))
                )
                if (claim.claim_type == "numerical" and valid_path and metadata_valid
                        and self._finite(actual) and self._finite(claim.expected_value)
                        and self._finite(claim.tolerance) and 0 <= claim.tolerance <= 1e-6
                        and abs(actual - claim.expected_value) <= claim.tolerance):
                    status = SUPPORTED
            claim.computed_value = actual
            claim.supported = status == SUPPORTED
            claim.verification_status = status
            unsupported += status == UNSUPPORTED
            checked.append(claim.to_dict())
        overall = (SUPPORTED if checked and not unsupported and not missing
                   else INSUFFICIENT_EVIDENCE if missing or not checked else UNSUPPORTED)
        return VerificationResult(overall, checked, unsupported, missing)
