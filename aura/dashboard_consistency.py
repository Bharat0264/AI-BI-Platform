"""Cross-dashboard semantic consistency and selective publication checks."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import math
from typing import Any

from .visualization_engine import VERIFIED, AMBIGUOUS, INVALID, INSUFFICIENT_EVIDENCE, UNSUPPORTED


@dataclass
class DashboardComponent:
    component_id: str
    component_type: str  # KPI, VISUALIZATION, FINDING
    evidence_id: str | None
    dataset_id: str | None
    dataset_version_id: str | None
    definition: dict[str, Any]
    aggregation: str | None
    filters: dict[str, Any]
    temporal_scope: Any
    currency: str | None
    unit: str | None
    verification_status: str
    displayed_value: float | None = None
    directly_comparable_group: str | None = None
    freshness: str = "CURRENT"

    def to_dict(self): return asdict(self)


def _issue(code, components, severity, invariant, explanation, action, safe=False, evidence=None):
    return {"code": code, "affected_components": components, "severity": severity, "invariant": invariant,
            "evidence_references": evidence or [], "explanation": explanation, "suggested_corrective_action": action,
            "automated_correction_safe": safe}


def _component(raw):
    return raw if isinstance(raw, DashboardComponent) else DashboardComponent(**raw)


def _finite(value): return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class DashboardConsistencyEngine:
    """Validates declared relationships only; different views are not conflicts by default."""
    def verify(self, components: list[DashboardComponent | dict], evidence: list[dict]) -> dict:
        items = [_component(item) for item in components]
        records = {item.get("evidence_id"): item for item in evidence}
        issues = []
        graph_nodes, graph_edges = [], []
        for item in items:
            graph_nodes.append({"id": item.component_id, "kind": item.component_type})
            if item.evidence_id: graph_edges.append({"from": item.evidence_id, "to": item.component_id, "relation": "supports"})
            if item.verification_status == AMBIGUOUS:
                issues.append(_issue("UNRESOLVED_AMBIGUITY", [item.component_id], "HIGH", "publication requires selected definition",
                    "This component is conditional on an unresolved business definition.", "Require user clarification.", False, [item.evidence_id]))
            elif item.verification_status in {INVALID, INSUFFICIENT_EVIDENCE, UNSUPPORTED}:
                issues.append(_issue("UNVERIFIED_COMPONENT", [item.component_id], "CRITICAL", "publication requires verified evidence",
                    f"Component verification status is {item.verification_status}.", "Recompute or remove the component.", False, [item.evidence_id]))
            if item.freshness != "CURRENT":
                issues.append(_issue("STALE_EVIDENCE", [item.component_id], "HIGH", "published evidence must be current",
                    "The component is bound to stale or unknown evidence.", "Review and recompute against the active snapshot.", False, [item.evidence_id]))
            record = records.get(item.evidence_id)
            if not record:
                issues.append(_issue("MISSING_EVIDENCE", [item.component_id], "CRITICAL", "every component has referenced evidence",
                    "Referenced evidence was not supplied to dashboard verification.", "Attach the immutable evidence record.", False, [item.evidence_id]))
                continue
            if record.get("dataset_id") != item.dataset_id or record.get("dataset_version_id", item.dataset_id) != item.dataset_version_id:
                issues.append(_issue("DATASET_VERSION_MISMATCH", [item.component_id], "CRITICAL", "component and evidence share dataset version",
                    "The component does not match its evidence dataset/version identity.", "Rebuild from the intended snapshot.", False, [item.evidence_id]))
            definition = record.get("definition", {})
            if definition.get("measure_column") != item.definition.get("measure_column") or definition.get("aggregation") != item.aggregation:
                issues.append(_issue("DEFINITION_OR_AGGREGATION_MISMATCH", [item.component_id], "CRITICAL", "displayed definition equals evidence definition",
                    "Metric column or aggregation differs from its evidence.", "Correct metadata or regenerate the component.", False, [item.evidence_id]))
            if record.get("filters", {}) != item.filters or definition.get("period") != item.temporal_scope:
                issues.append(_issue("SCOPE_MISMATCH", [item.component_id], "CRITICAL", "displayed scope equals evidence scope",
                    "Filters or temporal scope differ from evidence.", "Regenerate with the displayed scope.", False, [item.evidence_id]))
            if definition.get("currency") != item.currency or definition.get("unit") != item.unit:
                issues.append(_issue("CURRENCY_OR_UNIT_MISMATCH", [item.component_id], "CRITICAL", "displayed units equal evidence units",
                    "Currency or unit label conflicts with evidence.", "Correct labels or use a documented conversion.", False, [item.evidence_id]))
            expected = record.get("result", {}).get(item.aggregation)
            if item.component_type == "KPI" and item.displayed_value is not None and (_finite(expected) and not math.isclose(item.displayed_value, expected, rel_tol=0, abs_tol=1e-6)):
                issues.append(_issue("MISLEADING_NUMERICAL_SUMMARY", [item.component_id], "CRITICAL", "KPI value equals evidence aggregate",
                    "Displayed KPI does not equal its deterministic evidence result.", "Regenerate the KPI value.", True, [item.evidence_id]))
        # Only declared directly comparable views are compared; legitimate scoped/grouped differences stay silent.
        groups = {}
        for item in items:
            if item.directly_comparable_group: groups.setdefault(item.directly_comparable_group, []).append(item)
        for group, members in groups.items():
            anchor = members[0]
            for item in members[1:]:
                ids = [anchor.component_id, item.component_id]
                if anchor.dataset_id != item.dataset_id or anchor.dataset_version_id != item.dataset_version_id:
                    issues.append(_issue("CROSS_VIEW_DATASET_MISMATCH", ids, "CRITICAL", "direct comparison requires one dataset version",
                        "Directly comparable views use different snapshots.", "Separate the comparison or align snapshots.", False, [anchor.evidence_id, item.evidence_id]))
                if anchor.definition.get("term") == item.definition.get("term") and anchor.definition.get("measure_column") != item.definition.get("measure_column"):
                    issues.append(_issue("DIFFERENT_METRIC_DEFINITION", ids, "HIGH", "same business term requires selected common definition",
                        "Comparable views map the same term to different source columns.", "Require a shared definition or label both conditions.", False, [anchor.evidence_id, item.evidence_id]))
                if anchor.currency != item.currency or anchor.unit != item.unit:
                    issues.append(_issue("CROSS_VIEW_CURRENCY_OR_UNIT_CONFLICT", ids, "CRITICAL", "direct comparison requires compatible units",
                        "Comparable views use incompatible currency or unit assumptions.", "Apply an explicit verified conversion or separate views.", False, [anchor.evidence_id, item.evidence_id]))
                if anchor.filters != item.filters or anchor.temporal_scope != item.temporal_scope:
                    issues.append(_issue("DIRECT_COMPARISON_SCOPE_CONFLICT", ids, "HIGH", "direct comparison requires equal scope",
                        "Comparable views use different filters or time windows.", "Align scope or remove direct-comparison framing.", False, [anchor.evidence_id, item.evidence_id]))
                if anchor.aggregation != item.aggregation:
                    issues.append(_issue("INCONSISTENT_AGGREGATION_LEVEL", ids, "HIGH", "direct comparison requires equal aggregation",
                        "Comparable views use different aggregation levels.", "Use the same aggregation or disclose non-comparability.", False, [anchor.evidence_id, item.evidence_id]))
        severities = {issue["severity"] for issue in issues}
        gate = "REJECT" if "CRITICAL" in severities or "HIGH" in severities and any(i["code"] != "UNRESOLVED_AMBIGUITY" for i in issues) else "REQUIRE_CLARIFICATION" if issues else "PUBLISH_VERIFIED"
        if any(issue["code"] == "UNRESOLVED_AMBIGUITY" for issue in issues) and gate != "REJECT": gate = "REQUIRE_CLARIFICATION"
        return {"status": gate, "issues": issues, "components_checked": len(items), "coverage": "COMPLETE" if all(item.evidence_id in records for item in items) else "PARTIAL",
                "semantic_dependency_graph": {"nodes": graph_nodes + [{"id": key, "kind": "Evidence"} for key in records], "edges": graph_edges},
                "notice": "Findings are descriptive consistency checks; they do not establish causal root causes."}


def dashboard_detection_metrics(reports: list[dict], expected_issue_codes: list[set[str]]) -> dict:
    """Independent set-based metrics for labeled adversarial dashboards."""
    actual = [set(issue["code"] for issue in report["issues"]) for report in reports]
    tp = sum(len(a & e) for a, e in zip(actual, expected_issue_codes)); fp = sum(len(a - e) for a, e in zip(actual, expected_issue_codes)); fn = sum(len(e - a) for a, e in zip(actual, expected_issue_codes))
    return {"true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
            "false_positive_rate": fp / (tp + fp) if tp + fp else None, "coverage": sum(bool(report["components_checked"]) for report in reports) / len(reports) if reports else None}
