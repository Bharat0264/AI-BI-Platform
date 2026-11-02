"""Scoped execution reuses the deterministic calculator with frozen source semantics."""
from datetime import datetime, timezone
import math
from uuid import uuid4

from .provenance import EvidenceClaim
from .scopes import compile_scope, scope_sentence, ScopeError


def refusal(question, reason, scope=None):
    return {"status": "INSUFFICIENT DATA", "answer": "INSUFFICIENT DATA: " + reason,
            "plan": {"objective": question, "analytical_task": "unsupported", "required_columns": [], "filters": {}},
            "evidence": [], "claims": [], "verification": {"status": "NOT_RUN", "claims": []},
            "repair_attempts": 0, "request_scope": scope}


def decorate(engine, response, branch, request):
    response["request_scope"] = request
    predicate = branch["filters"]
    sentence = scope_sentence(predicate)
    old = " Scope: all supplied rows; no filters applied."
    response["answer"] = response["answer"].replace(old, sentence)
    response["plan"]["filters"] = predicate
    response["plan"]["scope_audit"] = branch["audit"]
    for item in response.get("alternatives", []):
        item["answer"] = item["answer"].replace(old, sentence)
    for evidence in response["evidence"]:
        evidence["filters"] = predicate
        evidence["scope"] = branch["audit"]
        evidence["source_columns"] = list(dict.fromkeys(evidence["source_columns"] + branch["source_columns"]))
        evidence["definition"]["filters"] = predicate["columns"]
        evidence["definition"]["period"] = predicate.get("date", "all supplied dates within selected filters")
    by_id = {e["evidence_id"]: e for e in response["evidence"]}
    for claim in response.get("claims", []):
        record = by_id[claim["evidence_id"]]
        claim["filters"] = record["filters"]
        claim["source_columns"] = record["source_columns"]
        claim["claim_text"] = claim["claim_text"].replace(old, sentence)
    if response["evidence"]:
        response["plan"]["required_columns"] = list(dict.fromkeys(column for e in response["evidence"] for column in e["source_columns"]))
    if engine.config["verifier"] and response.get("claims"):
        checked = engine.verifier.verify(response["claims"], response["evidence"]).to_dict()
        if checked["status"] != "SUPPORTED":
            return refusal(response["plan"]["objective"], "Scoped evidence did not verify.", request)
        response["claims"] = checked["claims"]
        response["verification"] = checked if response["status"] == "OK" else {**checked, "status": "CONDITIONAL"}
    return response


def answer_scoped(engine, question, df, dataset_id, corrections, definition, defaults, scope):
    if not df.columns.is_unique:
        return refusal(question, "Duplicate source column names must be resolved first.", scope)
    fields = engine.schema.infer(df, corrections) if engine.config["semantic"] else []
    try:
        compiled = compile_scope(df, fields, scope)
    except ScopeError as error:
        return refusal(question, str(error), scope)
    def calculate(frame):
        return engine._answer_unscoped(question, frame, dataset_id, corrections, definition, defaults, _fields=fields)
    if compiled is None:
        return calculate(df)
    current = decorate(engine, calculate(compiled["current"]["frame"]), compiled["current"], scope)
    if compiled["baseline"] is None:
        return current
    if current["status"] != "OK":
        if current["status"] == "CLARIFICATION_REQUIRED":
            current["answer"] = "Choose a measure before comparing periods. The alternatives below cover only the current period.\n" + current["answer"]
            current["interpretation_check"]["scope"] = "Current-period alternatives only; baseline comparison pending measure selection."
        return current
    parsed = current["plan"]["parsed_intent"]
    if parsed["dimension_alias"] is not None or parsed["direction"] is not None:
        return refusal(question, "Period comparison currently supports a single total or mean; grouped/ranked comparisons need an explicit supported plan.", scope)
    baseline = decorate(engine, calculate(compiled["baseline"]["frame"]), compiled["baseline"], scope)
    if baseline["status"] != "OK":
        return refusal(question, "The baseline period has no verified result: " + baseline["answer"], scope)
    if current["definition"].get("currency") != baseline["definition"].get("currency"):
        return refusal(question, "The periods use different or inconsistent currencies; an explicit conversion policy is required.", scope)
    if any(result["verification"]["status"] != "SUPPORTED" for result in (current, baseline)):
        return refusal(question, "Both period calculations must pass evidence verification.", scope)
    aggregation = current["definition"]["aggregation"]
    now = current["evidence"][0]["result"][aggregation]
    previous = baseline["evidence"][0]["result"][aggregation]
    difference = now - previous
    if not math.isfinite(difference):
        return refusal(question, "The period difference exceeds finite numerical limits.", scope)
    percentage = None
    percent_status = "UNDEFINED_ZERO_BASELINE" if previous == 0 else "NOT_REPORTED_NEGATIVE_BASELINE"
    if previous > 0:
        percentage = difference / previous * 100
        percent_status = "DEFINED" if math.isfinite(percentage) else "NOT_FINITE"
        if not math.isfinite(percentage):
            percentage = None
    columns = list(dict.fromkeys(current["evidence"][0]["source_columns"] + baseline["evidence"][0]["source_columns"]))
    filters = {"current": current["evidence"][0]["filters"], "baseline": baseline["evidence"][0]["filters"]}
    result = {"measure": current["definition"]["measure_column"], "aggregation": aggregation,
              "current": now, "baseline": previous, "difference": difference,
              "percent_change": percentage, "percent_change_status": percent_status,
              "difference_formula": "current - baseline", "percent_formula": "(current - baseline) / baseline * 100, only when baseline > 0",
              "direction": "increase" if difference > 0 else "decrease" if difference < 0 else "no change",
              "period_lengths": {key: value["date"]["calendar_days"] for key, value in filters.items()},
              "row_counts": {"current": current["evidence"][0]["result"]["rows"], "baseline": baseline["evidence"][0]["result"]["rows"]},
              "numeric_row_counts": {"current": current["evidence"][0]["result"]["valid_rows"], "baseline": baseline["evidence"][0]["result"]["valid_rows"]},
              "excluded_numeric_rows": {"current": current["evidence"][0]["result"]["excluded_rows"], "baseline": baseline["evidence"][0]["result"]["excluded_rows"]},
              "normalization": "None; totals are not normalized for different period lengths"}
    definition_record = {**current["definition"], "period": {key: value["date"] for key, value in filters.items()}}
    bindings = {"period_current": ["current"], "period_baseline": ["baseline"], "difference": ["difference"]}
    if percentage is not None:
        bindings["percent_change"] = ["percent_change"]
    evidence = {"evidence_id": str(uuid4()), "dataset_id": dataset_id, "analysis_type": "period comparison",
                "source_columns": columns, "filters": filters, "method": "deterministic period comparison",
                "result": result, "uncertainty": {"causal_claim": False, "source_completeness_established": False},
                "timestamp": datetime.now(timezone.utc).isoformat(), "result_bindings": bindings,
                "definition": definition_record, "semantic_corrections": dict(corrections or {}),
                "interpretation_status": "RESOLVED", "scope": {key: compiled[key]["audit"] for key in ("current", "baseline")},
                "dependency_evidence_ids": [current["evidence"][0]["evidence_id"], baseline["evidence"][0]["evidence_id"]]}
    text = (f"Verified period comparison for {result['measure']} ({aggregation}): current {now:,.2f}; baseline {previous:,.2f}; difference {difference:,.2f} ({result['direction']}). "
            + (f"Percentage change: {percentage:,.2f}%. " if percentage is not None else f"Percentage change not reported ({percent_status}). ")
            + scope_sentence(filters["current"]) + " Baseline:" + scope_sentence(filters["baseline"]).removeprefix(" Scope:")
            + f" Matching rows: {result['row_counts']['current']} current, {result['row_counts']['baseline']} baseline."
            + f" Numeric rows used: {result['numeric_row_counts']['current']} current, {result['numeric_row_counts']['baseline']} baseline; invalid numeric rows excluded: {result['excluded_numeric_rows']['current']} current, {result['excluded_numeric_rows']['baseline']} baseline."
            + f" Period lengths: {result['period_lengths']['current']} and {result['period_lengths']['baseline']} calendar days; totals are not normalized. Source completeness is not established.")
    claims = [EvidenceClaim.numeric(claim_text=f"{operation}: {result[path[0]]}", evidence=evidence,
                                   value=result[path[0]], operation=operation, result_path=path).to_dict()
              for operation, path in bindings.items()]
    all_evidence = current["evidence"] + baseline["evidence"] + [evidence]
    all_claims = current["claims"] + baseline["claims"] + claims
    checked = engine.verifier.verify(all_claims, all_evidence, columns).to_dict()
    if checked["status"] != "SUPPORTED":
        return refusal(question, "The comparison evidence did not verify.", scope)
    plan = {**current["plan"], "analytical_task": "period comparison", "required_columns": columns,
            "filters": filters, "comparison_formulas": {"difference": result["difference_formula"], "percent": result["percent_formula"]}}
    return {"status": "OK", "answer": text, "plan": plan, "evidence": all_evidence, "claims": checked["claims"],
            "verification": checked, "definition": definition_record, "comparison": result, "request_scope": scope,
            "repair_attempts": 0}
