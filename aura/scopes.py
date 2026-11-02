"""Validated row predicates and strict calendar-date windows for analyst queries."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256
import re

import numpy as np
import pandas as pd


DATE_FORMATS = {"ISO", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M",
                "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"}


class ScopeError(ValueError):
    pass


def calendar_window(raw):
    if not isinstance(raw, dict) or set(raw) != {"start", "end"}:
        raise ScopeError("A period needs exactly start and end ISO calendar dates.")
    try:
        if not all(isinstance(raw[key], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw[key]) for key in raw):
            raise ValueError()
        start, end = date.fromisoformat(raw["start"]), date.fromisoformat(raw["end"])
        if start > end:
            raise ValueError()
        exclusive = end + timedelta(days=1)
        left, right = pd.Timestamp(start).as_unit("ns"), pd.Timestamp(exclusive).as_unit("ns")
    except (ValueError, TypeError, OverflowError, pd.errors.OutOfBoundsDatetime) as error:
        raise ScopeError("Use valid start <= end ISO dates within the supported datetime range.") from error
    return {"start": start.isoformat(), "end": end.isoformat(), "end_exclusive": exclusive.isoformat(),
            "days": (end - start).days + 1}, left, right


def scope_options(df, fields):
    filters = []
    for field in fields:
        if field.semantic_role in {"region", "category"}:
            values = sorted({str(value) for value in df[field.column].dropna()})
            filters.append({"column": field.column, "role": field.semantic_role,
                            "values": values[:200], "truncated": len(values) > 200})
    return {"filter_columns": filters,
            "date_columns": [field.column for field in fields if field.semantic_role == "date/time"]}


def compile_scope(df, fields, raw):
    if raw is None or raw == {}:
        return None
    if not isinstance(raw, dict) or set(raw) - {"filters", "date_column", "period", "compare_to", "date_format"}:
        raise ScopeError("Scope supports only filters, date_column, period, compare_to and date_format.")
    filters = raw.get("filters", {})
    if not isinstance(filters, dict) or len(filters) > 2:
        raise ScopeError("Provide at most two explicit region/category column filters.")
    roles = {field.column: field.semantic_role for field in fields}
    positions = np.arange(len(df))
    mask = np.ones(len(df), dtype=bool)
    predicates = {}
    columns = []
    for column, requested in filters.items():
        if column not in df.columns or roles.get(column) not in {"region", "category"}:
            raise ScopeError("Filter columns must have confirmed region/category roles.")
        if (not isinstance(requested, list) or not requested or len(requested) > 200
                or not all(isinstance(value, str) and value for value in requested)):
            raise ScopeError("Each filter needs a nonempty list of up to 200 exact labels.")
        original = df[column]
        distinct = original.dropna().drop_duplicates()
        if len({str(value) for value in distinct}) != len(distinct):
            raise ScopeError("Filter labels collide as text; confirm unambiguous source labels first.")
        known = {str(value) for value in distinct}
        selected = sorted(set(requested))
        if not set(selected).issubset(known):
            raise ScopeError("A selected filter label does not exist in this dataset snapshot.")
        mask &= (original.notna() & original.astype(str).isin(selected)).to_numpy(dtype=bool)
        predicates[column] = selected
        columns.append(column)
    date_column = raw.get("date_column")
    period = raw.get("period")
    comparison = raw.get("compare_to")
    source_format = raw.get("date_format", "ISO")
    if not isinstance(source_format, str) or source_format not in DATE_FORMATS:
        raise ScopeError("Choose a supported explicit date format; automatic guessing is not available.")
    if "date_format" in raw and (date_column is None or period is None):
        raise ScopeError("A declared date format requires a date column and current period.")
    if comparison is not None and period is None:
        raise ScopeError("A comparison requires an explicit current period.")
    parsed_dates = None
    current_window = baseline_window = None
    if date_column is not None or period is not None:
        if not isinstance(date_column, str) or roles.get(date_column) != "date/time" or date_column not in df.columns:
            raise ScopeError("Choose an explicit date column with a date/time role.")
        current_window = calendar_window(period)
        if comparison is not None:
            baseline_window = calendar_window(comparison)
            if max(current_window[1], baseline_window[1]) < min(current_window[2], baseline_window[2]):
                raise ScopeError("Comparison periods must not overlap.")
        selected = df.iloc[positions[mask]][date_column]
        def valid(value):
            if isinstance(value, (datetime, pd.Timestamp)):
                return value.tzinfo is None
            if isinstance(value, date):
                return True
            if source_format != "ISO":
                if not isinstance(value, str):
                    return False
                try:
                    datetime.strptime(value, source_format)
                    return True
                except ValueError:
                    return False
            return isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?)?", value) is not None
        if selected.isna().any() or not all(valid(value) for value in selected.drop_duplicates()):
            raise ScopeError("Date-scoped rows require valid ISO dates or naive ISO timestamps; missing, ambiguous or timezone-aware dates need correction first.")
        try:
            parsed_dates = pd.to_datetime(selected, format="ISO8601", errors="raise") if source_format == "ISO" else pd.to_datetime(selected, format=source_format, errors="raise", exact=True)
        except (ValueError, TypeError, OverflowError) as error:
            raise ScopeError("A selected source date is invalid or outside the supported datetime range.") from error
        columns.append(date_column)
    elif comparison is not None:
        raise ScopeError("A comparison requires a date column and two periods.")
    if not predicates and current_window is None:
        raise ScopeError("An explicit scope must contain a filter or a date period.")
    selected_positions = positions[mask]
    def branch(window):
        chosen = selected_positions
        predicate = {"columns": predicates}
        if window is not None:
            bounds, left, right = window
            chosen = selected_positions[((parsed_dates >= left) & (parsed_dates < right)).to_numpy(dtype=bool)]
            predicate["date"] = {"column": date_column, "start_inclusive": bounds["start"],
                                 "end_exclusive": bounds["end_exclusive"], "end_inclusive": bounds["end"],
                                 "calendar_days": bounds["days"], "timezone_policy": "naive source calendar; no timezone conversion"}
            if source_format != "ISO":
                predicate["date"]["source_date_format"] = source_format
        if not len(chosen):
            raise ScopeError("The selected scope contains no rows; a missing period is not a measured zero.")
        digest = sha256(np.asarray(chosen, dtype="<i8").tobytes()).hexdigest()
        return {"frame": df.iloc[chosen].copy(), "filters": predicate,
                "source_columns": list(dict.fromkeys(columns)),
                "audit": {"source_rows": len(df), "selected_rows": len(chosen),
                          "row_position_sha256": digest, "row_position_basis": "zero-based source row order",
                          "period_coverage": "observed rows only; source completeness not established"}}
    return {"current": branch(current_window), "baseline": branch(baseline_window) if baseline_window else None,
            "request": raw}


def scope_sentence(predicate):
    parts = [f"{column} in [{', '.join(values)}]" for column, values in predicate.get("columns", {}).items()]
    if "date" in predicate:
        bounds = predicate["date"]
        parts.append(f"{bounds['column']} from {bounds['start_inclusive']} through {bounds['end_inclusive']} inclusive")
    return " Scope: " + "; ".join(parts) + "."
