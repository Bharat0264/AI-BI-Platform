"""Bounded comparisons of explicit column interpretations, without invented policies."""
from __future__ import annotations

import math

MAX_INTERPRETATIONS = 32
ABSOLUTE_TOLERANCE = 1e-6


def _same(left, right):
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=0, abs_tol=ABSOLUTE_TOLERANCE)
    return left == right


def compare_interpretations(candidates, execute, plan, role, term=None, impact_context=None):
    alternatives, evidence, claims, checked = [], [], [], []
    for column in candidates[:MAX_INTERPRETATIONS]:
        response = execute(column)
        item = {"measure_column": column, "status": response["status"], "answer": response["answer"],
                "evidence_ids": [e["evidence_id"] for e in response["evidence"]]}
        if response["status"] == "OK" and response["verification"]["status"] == "SUPPORTED":
            result = response["evidence"][0]["result"]
            operation = response["plan"]["aggregations"][0]
            # Compare the actual requested outputs, including the complete breakdown.
            comparison = {"value": result[operation]}
            if "ranking" in result:
                comparison["groups"] = result["ranking"]
            if "requested_result" in result:
                requested = result["requested_result"]
                comparison = {"value": requested["value"],
                              "winners": sorted(requested.get("ties", [requested["dimension"]]))}
            item.update(definition=response["definition"], comparison=comparison)
            checked.append(comparison)
        elif response["status"] == "OK":
            item["status"] = "UNVERIFIED"
        alternatives.append(item)
        for record in response["evidence"]:
            record["interpretation_status"] = "CONDITIONAL"
            record["evidence_role"] = "CONDITIONAL_CANDIDATE"
            record["report_eligible"] = True
        evidence.extend(response["evidence"])
        claims.extend(response.get("claims", []))
    complete = len(candidates) <= MAX_INTERPRETATIONS and len(checked) == len(candidates)
    impact = ("SAME_TESTED_OUTPUT" if all(_same(checked[0], item) for item in checked[1:])
              else "DIFFERENT_TESTED_OUTPUTS") if complete else "UNDETERMINED"
    all_failed = len(alternatives) == len(candidates) and all(
        item["status"] == "INSUFFICIENT DATA" for item in alternatives)
    lines = (["INSUFFICIENT DATA: none of the detected measure interpretations could be computed."]
             if all_failed else ["Clarification required: which column should define this measure?"])
    for item in alternatives:
        lines.append(f"If you mean {item['measure_column']}: {item['answer']}")
    if impact == "SAME_TESTED_OUTPUT":
        lines.append("The tested outputs agree within an absolute tolerance of 0.000001. This does not establish that the columns have the same business meaning.")
    elif impact == "DIFFERENT_TESTED_OUTPUTS":
        lines.append("The answer changes with the selected column.")
    else:
        lines.append("Comparison coverage is incomplete; no stability conclusion is available.")
    lines.append("Ask again using the exact column name to choose a definition.")
    options = [{"measure_column": column, "definition": {"measure_column": column}} for column in candidates]
    response = {"status": "INSUFFICIENT DATA" if all_failed else "CLARIFICATION_REQUIRED", "answer": "\n".join(lines), "plan": plan,
            "evidence": evidence, "claims": claims, "repair_attempts": 0,
            "verification": {"status": "CONDITIONAL", "claims": [],
                             "notice": "Each successful interpretation has separate verified evidence; no interpretation has been selected."},
            "alternatives": alternatives,
            "interpretation_check": {"impact": impact, "coverage": "COMPLETE" if complete else "PARTIAL",
                                     "candidate_count": len(candidates), "executed_count": len(alternatives),
                                     "absolute_tolerance": ABSOLUTE_TOLERANCE,
                                     "scope": "Detected measure columns only; not all possible business definitions."},
            "clarification": {"field": "measure_column", "semantic_role": role, "term": term,
                              "question": "Which column should define this measure?", "options": options}}
    if impact_context is not None:
        from .impact import analyze_semantic_interpretation_impact
        impact = analyze_semantic_interpretation_impact(candidates=candidates, semantic_role=role,
            business_term=term or role, requested_aggregation=plan["aggregations"][0], **impact_context)
        response["semantic_interpretation_impact"] = impact
        # Conditional chart contracts are additive research output. They remain
        # explicitly ambiguous until a user chooses a candidate definition.
        from .visualization_engine import EvidenceVerifiedVisualizationEngine
        response["conditional_visualizations"] = EvidenceVerifiedVisualizationEngine().conditional_from_impact(impact)
        impact_evidence = [candidate["evidence"] for candidate in impact["candidates"] if "evidence" in candidate]
        for record in impact_evidence:
            # Broader grouped/ranking/chart diagnostics are inspectable lineage,
            # not a second candidate conclusion for report selection.
            record["evidence_role"] = "INTERPRETATION_IMPACT_DIAGNOSTIC"
            record["report_eligible"] = False
        impact_claims = [claim for candidate in impact["candidates"] for claim in candidate.get("verification", {}).get("claims", [])]
        response["evidence"].extend(impact_evidence)
        response["claims"].extend(impact_claims)
    return response
