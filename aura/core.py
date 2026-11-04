"""Evidence-first services for heterogeneous business data."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4
import re
import warnings
import numpy as np
import pandas as pd
from date_utils import parse_business_dates
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score, mean_squared_error, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from .provenance import EvidenceClaim
from .verifier import EvidenceVerifier
from .interpretations import compare_interpretations
from .questions import parse_question
from .scoped_engine import answer_scoped


ROLE_TERMS = {
    "date/time": ("date", "time", "month", "year", "timestamp"),
    "identifier": ("id", "uuid", "code", "number", "invoice", "order"),
    "revenue": ("revenue", "sales", "gmv", "turnover", "amount", "merchandise value", "recognized income", "attributed", "basket value", "realized value", "billing amount"),
    "profit": ("profit", "margin", "earnings", "income"),
    "cost": ("cost", "cogs", "expense", "spend", "freight"),
    "quantity": ("quantity", "qty", "units", "volume", "demand"),
    "price": ("price", "rate", "unit price"),
    "customer": ("customer", "client", "buyer", "account"),
    "product": ("product", "sku", "item", "brand"),
    "category": ("category", "department", "segment", "type", "class", "family", "group", "vertical", "source"),
    "region": ("region", "market", "state", "country", "city", "territory", "location", "business unit", "office", "hub", "audience", "delivery", "factory", "service area"),
    "channel": ("channel", "source", "campaign", "platform"),
    "target/outcome": ("target", "label", "outcome", "churn", "converted", "status"),
}

@dataclass
class SemanticField:
    column: str
    semantic_role: str
    confidence: float
    reason: str
    signals: dict | None = None

@dataclass
class AnalyticsEvidence:
    evidence_id: str
    dataset_id: str
    analysis_type: str
    source_columns: list[str]
    filters: dict
    method: str
    result: dict
    uncertainty: dict
    timestamp: str

    @classmethod
    def create(cls, dataset_id, analysis_type, columns, method, result, filters=None, uncertainty=None):
        return cls(str(uuid4()), dataset_id, analysis_type, list(columns), filters or {}, method, result, uncertainty or {}, datetime.now(timezone.utc).isoformat())

def _name(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()

def _date_parseability(series):
    # Profiling needs only a parseable/not-parseable signal, never converted dates.
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        try:
            return parse_business_dates(series).notna().mean()
        except (ValueError, TypeError, FutureWarning):
            return pd.to_datetime(series, format="mixed", errors="coerce", utc=True).notna().mean()


class SemanticSchemaEngine:
    def infer(self, df: pd.DataFrame, corrections: dict | None = None) -> list[SemanticField]:
        corrections = corrections or {}
        fields = []
        for column in df.columns:
            series, label = df[column], _name(column)
            if column in corrections:
                fields.append(SemanticField(column, corrections[column], 1.0, "User-confirmed workspace definition", {"user_correction": 1.0})); continue
            numeric = pd.to_numeric(series, errors="coerce").notna().mean()
            dates = 1.0 if pd.api.types.is_datetime64_any_dtype(series) else (_date_parseability(series) if series.dtype == object else 0)
            uniqueness = series.nunique(dropna=True) / max(len(series), 1)
            cardinality = series.nunique(dropna=True)
            categorical_ratio = cardinality / max(len(series), 1)
            signals = {"name": 0.0, "datatype": float(numeric), "date_parseability": float(dates), "uniqueness": float(uniqueness), "cardinality_ratio": float(categorical_ratio)}
            scores = {role: 0.0 for role in ROLE_TERMS}
            for role, terms in ROLE_TERMS.items():
                hits = [term for term in terms if term in label]
                if hits:
                    scores[role] += min(.78, .58 + .12 * len(hits)); signals[f"name:{role}"] = scores[role]
            # Date labels are more specific than an incidental "order" token in
            # a label such as "Order Date"; identifier uniqueness must not win.
            if any(term in label for term in ROLE_TERMS["date/time"]):
                scores["date/time"] += .5
            scores["date/time"] += .72 * dates
            scores["identifier"] += .42 * uniqueness if cardinality > 5 and dates < .3 else 0
            if any(token in label for token in (" id", "_id", "key", "ref", "code", "token", "reading")):
                scores["identifier"] += .45
            if any(token in label for token in ("class", "family", "group", "vertical")):
                scores["category"] += .35
            # Numeric business measures normally have substantial numeric coverage;
            # categorical fields have modest cardinality relative to records.
            for role in ("revenue", "profit", "cost", "quantity", "price"):
                scores[role] += .12 * numeric
            for role in ("customer", "product", "category", "region", "channel"):
                scores[role] += .08 if categorical_ratio < .65 else 0
            role, score = max(scores.items(), key=lambda item: item[1])
            identifier_hint = any(token in label for token in ("id", "uuid", "code", "number", "invoice", "order", "key", "ref", "token"))
            if role == "identifier" and not identifier_hint and numeric >= .8:
                role, score = "generic numerical", .66
            if score < .35:
                role = "generic numerical" if numeric >= .8 else "generic categorical"
                score = .66 if numeric >= .8 else .62
                reason = "Numeric coverage" if numeric >= .8 else "Categorical value pattern without a confident business-role match"
            else:
                evidence = [key for key, value in signals.items() if value and (key == "name" or key.startswith("name:"))]
                reason = f"Fused name, type, parseability, cardinality and uniqueness signals ({', '.join(evidence) or 'distribution signals'})"
            confidence = round(float(min(.99, max(.05, score))), 3)
            fields.append(SemanticField(column, role, confidence, reason, signals))
        return fields

    def profile(self, df: pd.DataFrame) -> dict:
        columns = {}
        for c in df.columns:
            s = df[c]
            columns[c] = {"dtype": str(s.dtype), "null_percent": round(float(s.isna().mean() * 100), 2), "unique_count": int(s.nunique(dropna=True))}
            if pd.api.types.is_numeric_dtype(s): columns[c]["statistics"] = {k: (None if pd.isna(v) else round(float(v), 4)) for k, v in s.describe().to_dict().items()}
        numeric = df.select_dtypes(include=np.number)
        high_missing = [c for c in df.columns if df[c].isna().mean() > .3]
        warnings = (["Duplicate rows detected"] if df.duplicated().any() else []) + (["High missingness: " + ", ".join(high_missing)] if high_missing else [])
        return {"rows": len(df), "columns": len(df.columns), "duplicates": int(df.duplicated().sum()), "column_profile": columns, "quality_warnings": warnings, "correlations": numeric.corr().round(3).replace({np.nan: None}).to_dict() if len(numeric.columns) > 1 else {}}

class KPIEngine:
    def discover(self, df, fields):
        by_role = {f.semantic_role: f.column for f in fields}
        out = []
        def add(name, formula, cols, value, why): out.append({"name": name, "formula": formula, "source_columns": cols, "filters": {}, "computed_value": float(value), "applicability_reason": why})
        if "revenue" in by_role: add("Revenue", f"SUM({by_role['revenue']})", [by_role['revenue']], pd.to_numeric(df[by_role['revenue']], errors="coerce").sum(), "Revenue semantic role detected")
        if "profit" in by_role: add("Profit", f"SUM({by_role['profit']})", [by_role['profit']], pd.to_numeric(df[by_role['profit']], errors="coerce").sum(), "Profit semantic role detected")
        if "revenue" in by_role and "profit" in by_role:
            sales = pd.to_numeric(df[by_role['revenue']], errors="coerce").sum(); profit = pd.to_numeric(df[by_role['profit']], errors="coerce").sum()
            if sales: add("Profit Margin", f"SUM({by_role['profit']}) / SUM({by_role['revenue']})", [by_role['profit'], by_role['revenue']], profit / sales, "Profit and revenue available")
        if "identifier" in by_role: add("Records", f"COUNT(DISTINCT {by_role['identifier']})", [by_role['identifier']], df[by_role['identifier']].nunique(), "Identifier semantic role detected")
        if "customer" in by_role: add("Customer Count", f"COUNT(DISTINCT {by_role['customer']})", [by_role['customer']], df[by_role['customer']].nunique(), "Customer role detected")
        return out

class AnalyticsPlanner:
    def plan(self, objective, fields):
        q = objective.lower(); roles = {f.semantic_role: f.column for f in fields}
        task = "descriptive statistics"; chart = "bar"
        if any(w in q for w in ("trend", "over time", "monthly", "decrease", "increase")): task, chart = "time trends", "line"
        elif any(w in q for w in ("forecast", "predict")): task, chart = "forecasting", "line"
        elif any(w in q for w in ("anomaly", "unusual", "why did")): task, chart = "anomaly investigation", "bar"
        elif any(w in q for w in ("correlation", "relationship")): task, chart = "correlation", "scatter"
        elif any(w in q for w in ("rank", "top", "lowest", "by ")): task, chart = "ranking", "bar"
        required = [v for r, v in roles.items() if r in {"revenue", "profit", "date/time", "category", "region"}]
        return {"objective": objective, "analytical_task": task, "required_columns": required, "filters": {}, "aggregations": ["sum"], "statistical_method": "deterministic pandas aggregation", "visualization": chart, "validation_rules": ["required source columns must exist", "all numerical claims require evidence"]}

class VisualizationEngine:
    def recommend(self, fields):
        roles = {f.semantic_role: f.column for f in fields}; recs=[]
        if "date/time" in roles and any(r in roles for r in ("revenue", "profit", "quantity")): recs.append({"chart_type":"line","x":roles["date/time"],"y":next(roles[r] for r in ("revenue","profit","quantity") if r in roles),"aggregation":"sum","reasoning":"Time with business measure","confidence":.94})
        if any(r in roles for r in ("category","region")) and any(r in roles for r in ("revenue","profit","quantity")): recs.append({"chart_type":"bar","x":next(roles[r] for r in ("category","region") if r in roles),"y":next(roles[r] for r in ("revenue","profit","quantity") if r in roles),"aggregation":"sum","reasoning":"Business dimension with measure","confidence":.9})
        return recs

class AnomalyEngine:
    def investigate(self, df, fields, dataset_id="active"):
        numeric = [f.column for f in fields if f.semantic_role in {"revenue","profit","cost","quantity","generic numerical"}]
        if not numeric or len(df) < 8: return None
        x = df[numeric].apply(pd.to_numeric, errors="coerce").fillna(0)
        labels = IsolationForest(contamination="auto", random_state=42).fit_predict(x)
        count = int((labels == -1).sum())
        return AnalyticsEvidence.create(dataset_id, "anomaly investigation", numeric, "Isolation Forest; diagnostic only", {"anomalous_records": count, "affected_columns": numeric}, uncertainty={"causal_claim": False})

    def root_cause(self, df, fields, dataset_id="active"):
        roles={f.semantic_role:f.column for f in fields}; measure=roles.get("revenue") or roles.get("profit")
        date_col=roles.get("date/time")
        if not measure or not date_col:
            return None, "INSUFFICIENT DATA: a date/time field and revenue or profit field are required."
        work=df.copy(); work["_date"]=parse_business_dates(work[date_col]); work["_value"]=pd.to_numeric(work[measure],errors="coerce").fillna(0)
        work=work.dropna(subset=["_date"])
        if work.empty: return None, "INSUFFICIENT DATA: date values could not be interpreted."
        work["_period"]=work["_date"].dt.to_period("M")
        totals=work.groupby("_period")["_value"].sum().sort_index()
        if len(totals)<2: return None, "INSUFFICIENT DATA: at least two monthly periods are required."
        current,previous=totals.iloc[-1],totals.iloc[-2]; delta=float(current-previous); pct=float(delta/previous) if previous else None
        if delta >= 0:
            result={"measure":measure,"current_period":str(totals.index[-1]),"comparison_period":str(totals.index[-2]),"change":delta,"change_percent":pct,"premise_verified":False,"contributors":[]}
            return AnalyticsEvidence.create(dataset_id,"root-cause investigation",[measure,date_col],"period comparison; diagnostic only",result,uncertainty={"causal_claim":False}), "No decrease was observed in the latest complete comparison period."
        contributors=[]
        for role in ("region","category","product","customer","channel"):
            column=roles.get(role)
            if not column: continue
            pivot=work[work["_period"].isin(totals.index[-2:])].groupby(["_period",column])["_value"].sum().unstack(fill_value=0)
            diff=(pivot.reindex(totals.index[-2:],fill_value=0).iloc[-1]-pivot.reindex(totals.index[-2:],fill_value=0).iloc[-2]).sort_values()
            for item,value in diff.head(3).items():
                if value < 0: contributors.append({"dimension":column,"segment":str(item),"change":float(value),"share_of_total_change":float(abs(value/delta))})
        contributors=sorted(contributors,key=lambda x:x["change"])[:8]
        result={"measure":measure,"current_period":str(totals.index[-1]),"comparison_period":str(totals.index[-2]),"change":delta,"change_percent":pct,"premise_verified":True,"contributors":contributors}
        evidence=AnalyticsEvidence.create(dataset_id,"root-cause investigation",[measure,date_col]+[x["dimension"] for x in contributors],"monthly contribution decomposition; diagnostic association only",result,uncertainty={"causal_claim":False})
        return evidence, f"Verified {measure} decreased by {abs(pct or 0):.1%}. Ranked segments are associated with, and explain part of, the observed difference; they are not causal effects."

class AutoMLEngine:
    def infer_task(self, df, target):
        if target not in df: return "invalid"
        y=df[target]
        if pd.api.types.is_numeric_dtype(y) and y.nunique() > 12: return "regression"
        return "binary classification" if y.nunique() == 2 else "multiclass classification"
    def train(self, df, target):
        if target not in df or len(df) < 12:
            raise ValueError("A valid target and at least 12 rows are required.")
        work = df.dropna(subset=[target]).copy()
        if len(work) < 12:
            raise ValueError("The selected target needs at least 12 non-empty values.")
        # Bound training work deterministically. This prevents high-cardinality identifiers
        # (for example Order ID) from expanding into an unsafe one-hot feature matrix.
        if len(work) > 25_000:
            work = work.sample(n=25_000, random_state=42)
        task=self.infer_task(work,target)
        y=work[target]
        if y.nunique(dropna=True) < 2:
            raise ValueError("The selected target must contain at least two distinct values.")
        if task != "regression":
            class_counts = y.value_counts(dropna=True)
            if y.nunique() > 30 or class_counts.min() < 2:
                raise ValueError("Classification targets need no more than 30 classes and at least two rows in every class.")

        features = pd.DataFrame(index=work.index)
        excluded = []
        for column in work.columns:
            if column == target:
                continue
            series = work[column]
            numeric = pd.to_numeric(series, errors="coerce")
            numeric_ratio = numeric.notna().mean()
            cardinality = series.nunique(dropna=True)
            uniqueness = cardinality / max(len(work), 1)
            if numeric_ratio >= .9:
                features[column] = numeric.replace([np.inf, -np.inf], np.nan).fillna(0)
            elif cardinality <= 40 and uniqueness < .95:
                features[column] = series.astype("string").fillna("(missing)")
            else:
                excluded.append(column)
        if features.empty:
            raise ValueError("No safe predictive features remain after excluding identifiers and high-cardinality fields.")
        x = pd.get_dummies(features, dummy_na=True, dtype=float).replace([np.inf, -np.inf], np.nan).fillna(0)
        if x.shape[1] > 250:
            raise ValueError("The selected data produces too many encoded features. Exclude high-cardinality columns before training.")
        Xtr,Xte,ytr,yte=train_test_split(x,y,test_size=.25,random_state=42, stratify=y if task != "regression" else None)
        model = RandomForestRegressor(n_estimators=80,random_state=42) if task=="regression" else RandomForestClassifier(n_estimators=80,random_state=42)
        model.fit(Xtr,ytr); pred=model.predict(Xte)
        if task=="regression":
            metrics={"mae":float(mean_absolute_error(yte,pred)),"rmse":float(mean_squared_error(yte,pred)**.5),"r2":float(r2_score(yte,pred))}
        else:
            precision,recall,f1,_=precision_recall_fscore_support(yte,pred,average="weighted",zero_division=0)
            metrics={"accuracy":float(accuracy_score(yte,pred)),"precision":float(precision),"recall":float(recall),"f1":float(f1)}
        return {"task":task,"model":"RandomForest","metrics":metrics,"feature_importance":dict(sorted(zip(x.columns,model.feature_importances_),key=lambda z:z[1],reverse=True)[:10]),"training_rows":int(len(work)),"feature_count":int(x.shape[1]),"excluded_features":excluded,"causal_claim":False}

class AuraOrchestrator:
    def __init__(self, config=None):
        self.config = {"semantic": True, "planner": True, "provenance": True, "verifier": True, "repair": True, **(config or {})}
        self.schema=SemanticSchemaEngine(); self.kpis=KPIEngine(); self.planner=AnalyticsPlanner(); self.visuals=VisualizationEngine(); self.anomalies=AnomalyEngine(); self.ml=AutoMLEngine(); self.verifier=EvidenceVerifier()
    def inspect(self, df, dataset_id="active", corrections=None):
        fields=self.schema.infer(df, corrections) if self.config["semantic"] else []
        anomaly=self.anomalies.investigate(df, fields, dataset_id)
        return {"profile":self.schema.profile(df),"semantic_schema":[asdict(f) for f in fields],"kpis":self.kpis.discover(df,fields),"visualizations":self.visuals.recommend(fields),"anomaly_evidence":asdict(anomaly) if anomaly else None}
    def answer(self, question, df, dataset_id="active", corrections=None, definition=None, saved_definitions=None, scope=None):
        return answer_scoped(self, question, df, dataset_id, corrections, definition, saved_definitions, scope)

    def _answer_unscoped(self, question, df, dataset_id="active", corrections=None, definition=None, saved_definitions=None, _fields=None):
        fields = _fields if _fields is not None else self.schema.infer(df, corrections) if self.config["semantic"] else []
        plan = {"objective": question, "analytical_task": "unsupported", "required_columns": [],
                "filters": {}, "aggregations": [], "validation_rules": ["exact result binding"]}

        def reject(reason):
            return {"status": "INSUFFICIENT DATA", "answer": "INSUFFICIENT DATA: " + reason,
                    "plan": plan, "evidence": [], "claims": [],
                    "verification": {"status": "NOT_RUN", "claims": []}, "repair_attempts": 0}

        if definition is not None and (not isinstance(definition, dict)
                or set(definition) != {"measure_column"}
                or not isinstance(definition["measure_column"], str)):
            return reject("A definition must contain only a measure_column string.")
        if not df.columns.is_unique:
            return reject("Duplicate column names must be resolved first.")
        measure_terms = {"revenue": "revenue", "sales": "revenue", "profit": "profit",
                         "cost": "cost", "costs": "cost", "quantity": "quantity"}
        aliases = dict(measure_terms)
        field_roles = {}
        dimension_aliases = {"region": "region", "regions": "region", "regional": "region",
                             "category": "category", "categories": "category"}
        dimension_roles = {}
        for field in fields:
            name = _name(field.column)
            if field.semantic_role in {"revenue", "profit", "cost", "quantity"}:
                aliases[name] = field.semantic_role
                field_roles.setdefault(name, set()).add(field.semantic_role)
            if field.semantic_role in {"region", "category"}:
                dimension_aliases[name] = field.semantic_role
                dimension_roles.setdefault(name, set()).add(field.semantic_role)
        intent = parse_question(question, aliases, dimension_aliases)
        if intent is None:
            return reject("No complete supported plan could be resolved. Ask for a total, average, grouping or highest/lowest group. Dates, filters, forecasts, ratios and causes require separate supported operations.")
        alias = intent.measure_alias
        if len(field_roles.get(alias, set())) > 1:
            return reject("Column names normalize to conflicting business roles. Confirm unambiguous names first.")
        dimension_role = dimension_aliases.get(intent.dimension_alias)
        if len(dimension_roles.get(intent.dimension_alias, set())) > 1:
            return reject("Grouping names normalize to conflicting business roles.")
        ranked = intent.direction is not None
        direction = intent.direction
        aggregation = intent.aggregation
        operation = "ranking" if ranked else aggregation
        plan["parsed_intent"] = intent.to_dict()
        role = aliases[alias]
        saved_reference = None
        candidates = [f.column for f in fields if f.semantic_role == role]
        exact = [column for column in candidates if _name(column) == alias]
        if len(exact) == 1:
            candidates = exact
        if definition is not None:
            selected = definition["measure_column"]
            if selected not in candidates:
                return reject("The chosen column is not an admissible interpretation of this question.")
            candidates = [selected]
        elif not exact and isinstance(saved_definitions, dict) and alias in saved_definitions:
            saved = saved_definitions[alias]
            if (not isinstance(saved, dict) or saved.get("active") is not True
                    or saved.get("dataset_id") != dataset_id
                    or saved.get("semantic_role") != role
                    or saved.get("measure_column") not in candidates):
                return reject("The saved definition is no longer admissible. Review and confirm a new definition.")
            candidates = [saved["measure_column"]]
            saved_reference = {key: saved[key] for key in
                               ("definition_id", "version", "workspace_id", "dataset_id", "term")}
        if not candidates:
            return reject("The requested measure is missing; confirm its column and semantic role.")
        if len(candidates) > 1:
            plan.update(analytical_task="interpretation comparison", required_columns=candidates,
                        aggregations=[aggregation])
            return compare_interpretations(
                candidates,
                lambda column: self._answer_unscoped(question, df, dataset_id, corrections,
                                           definition={"measure_column": column}, _fields=fields),
                plan, role, term=alias,
                impact_context={"df": df, "dataset_id": dataset_id, "dimensions": [field.column for field in fields if field.semantic_role in {"region", "category"}], "verifier": self.verifier})
        col = candidates[0]
        # A rate/margin is not an additive profit amount.
        if "%" in str(col) or any(token in _name(col).split() for token in ("margin", "percent", "percentage", "pct", "rate")):
            return reject("Rate and margin calculations require an explicit formula.")
        dimension = None
        if dimension_role:
            dimensions = [f.column for f in fields if f.semantic_role == dimension_role]
            exact_dimensions = [column for column in dimensions if _name(column) == intent.dimension_alias]
            if len(exact_dimensions) == 1:
                dimensions = exact_dimensions
            if len(dimensions) != 1:
                return reject("The requested grouping column is missing or ambiguous.")
            dimension = dimensions[0]
        if any(isinstance(value, (bool, np.bool_)) for value in df[col].dropna()):
            return reject("Boolean flags cannot be treated as business amounts.")
        values = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        if not values.notna().any():
            return reject("The requested measure has no finite numeric observations.")
        currency_columns = []
        currency = None
        if role in {"revenue", "profit", "cost"}:
            currency_columns = [column for column in df.columns if _name(column) in {"currency", "currency code", "iso currency"}]
            for currency_column in currency_columns:
                codes = df.loc[values.notna(), currency_column]
                if codes.isna().any() or not all(isinstance(code, str) and re.fullmatch(r"[A-Za-z]{3}", code.strip()) for code in codes):
                    return reject("Monetary observations need explicit, consistent currency codes when a currency column is supplied.")
                observed = {code.strip().upper() for code in codes}
                if len(observed) != 1 or (currency is not None and currency not in observed):
                    return reject("Multiple or conflicting currencies require an explicit conversion policy.")
                currency = next(iter(observed))
        columns = [col] + ([dimension] if dimension else []) + currency_columns
        plan.update(analytical_task="ranking" if ranked else "descriptive statistics",
                    required_columns=columns, aggregations=[aggregation],
                    statistical_method="pandas " + aggregation)
        result = {"measure": col, "sum": float(values.sum()), "mean": float(values.mean()),
                  "rows": int(len(df)), "valid_rows": int(values.notna().sum()),
                  "excluded_rows": int(values.isna().sum())}
        if not all(np.isfinite(result[key]) for key in ("sum", "mean")):
            return reject("The requested calculation overflowed finite numeric limits.")
        claims = []
        bindings = {"sum": ["sum"], "mean": ["mean"]}
        if dimension:
            if df[dimension].isna().any():
                return reject("Missing grouping values must be resolved before a complete breakdown can be verified.")
            grouped = df.assign(_aura_value=values).groupby(dimension)["_aura_value"]
            grouped = grouped.sum(min_count=1) if aggregation == "sum" else grouped.mean()
            if len({str(label) for label in grouped.index}) != len(grouped):
                return reject("Distinct group labels collide when represented as text. Confirm unambiguous grouping labels first.")
            if not np.isfinite(grouped.to_numpy()).all():
                return reject("One or more groups have no finite result.")
            lowest = bool(ranked and direction in {"lowest", "least"})
            grouped = grouped.sort_values(ascending=lowest)
            result.update(grouped_by=dimension, ranking={str(k): float(v) for k, v in grouped.items()})
            if ranked:
                winners = [str(key) for key, value in grouped.items() if value == grouped.iloc[0]]
                result["requested_result"] = {"direction": "lowest" if lowest else "highest",
                                              "dimension": winners[0], "value": float(grouped.iloc[0])}
                if len(winners) > 1:
                    result["requested_result"]["ties"] = winners
                bindings["ranking"] = ["requested_result", "value"]
                text = f"Verified result: {', '.join(winners)} has the {result['requested_result']['direction']} {'average ' if aggregation == 'mean' else ''}{col} at {grouped.iloc[0]:,.2f}."
            else:
                text = f"Verified result: {col} {'averages' if aggregation == 'mean' else 'totals'} {result[aggregation]:,.2f}. Breakdown by {dimension} is included in the evidence."
        else:
            text = f"Verified result: {col} {'averages' if aggregation == 'mean' else 'totals'} {result[aggregation]:,.2f} across {result['valid_rows']:,} numeric rows."
        if result["excluded_rows"]:
            text += f" Excluded {result['excluded_rows']} missing, invalid or non-finite values."
        text += " Scope: all supplied rows; no filters applied."
        evidence = asdict(AnalyticsEvidence.create(dataset_id, plan["analytical_task"], columns,
                         "pandas " + aggregation, result, uncertainty={"causal_claim": False}))
        evidence["result_bindings"] = bindings
        definition_record = {"term": alias, "measure_column": col, "semantic_role": role,
                             "aggregation": aggregation, "grouping_column": dimension,
                             "filters": {}, "period": "all supplied rows",
                             "missing_value_policy": "exclude missing, invalid and non-finite measure values",
                             "selection": "saved definition" if saved_reference else "explicit" if definition is not None or exact else "single detected candidate"}
        if currency:
            definition_record["currency"] = currency
            text += f" Currency: {currency}."
        if saved_reference:
            definition_record["saved_reference"] = saved_reference
            text += f" Using saved definition {alias}, version {saved_reference['version']}: {col}."
        evidence["definition"] = definition_record
        evidence["semantic_corrections"] = dict(corrections or {})
        evidence["interpretation_status"] = "RESOLVED"
        path = bindings[operation]
        value = result["requested_result"]["value"] if ranked else result[aggregation]
        if self.config["provenance"]:
            claims = [EvidenceClaim.numeric(claim_text=text, evidence=evidence, value=value,
                                            operation=operation, result_path=path).to_dict()]
        verification = {"status": "NOT_RUN", "claims": [], "unsupported_claim_count": 0, "missing_evidence_count": 0}
        if self.config["verifier"] and claims:
            verification = self.verifier.verify(claims, [evidence], columns).to_dict()
            claims = verification["claims"]
            if verification["status"] != "SUPPORTED":
                return reject("The calculation could not be bound to verified evidence.")
        return {"status": "OK", "answer": text, "plan": plan, "evidence": [evidence],
                "claims": claims, "verification": verification, "repair_attempts": 0,
                "definition": definition_record}

    def run_analysis(self, objective, df, dataset_id="active", dimension=None, measure=None):
        fields=self.schema.infer(df); roles={f.semantic_role:f.column for f in fields}; plan=self.planner.plan(objective,fields)
        measure=measure or roles.get("revenue") or roles.get("profit") or next((f.column for f in fields if f.semantic_role=="generic numerical"),None)
        if not measure or measure not in df: raise ValueError("Choose a numeric measure available in the dataset.")
        values=pd.to_numeric(df[measure],errors="coerce").replace([np.inf,-np.inf],np.nan)
        if values.notna().sum() == 0:
            raise ValueError(f"'{measure}' does not contain numeric values. Select a revenue, profit, quantity, price, or other numeric measure.")
        result={"measure":measure,"rows":int(len(df)),"sum":float(values.sum()),"mean":float(values.mean())}; columns=[measure]
        if dimension and dimension in df:
            grouped=df.assign(_aura_value=values).groupby(dimension)["_aura_value"].sum().sort_values(ascending=False).head(25)
            result["dimension"]=dimension; result["series"]={str(k):float(v) for k,v in grouped.items()}; columns.append(dimension)
        evidence=AnalyticsEvidence.create(dataset_id,plan["analytical_task"],columns,"pandas aggregation",result,uncertainty={"causal_claim":False})
        return {"plan":plan,"evidence":asdict(evidence),"visualization":{"chart_type":"bar" if dimension else "histogram","x":dimension,"y":measure,"reasoning":"Selected from the computed dimension and measure."}}
