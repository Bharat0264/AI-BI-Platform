"""Evidence-first services for heterogeneous business data."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4
import re
import numpy as np
import pandas as pd
from date_utils import parse_business_dates
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score, mean_squared_error, precision_recall_fscore_support
from sklearn.model_selection import train_test_split


ROLE_TERMS = {
    "date/time": ("date", "time", "month", "year", "timestamp"),
    "identifier": ("id", "uuid", "code", "number", "invoice", "order"),
    "revenue": ("revenue", "sales", "gmv", "turnover", "amount", "merchandise value"),
    "profit": ("profit", "margin", "earnings", "income"),
    "cost": ("cost", "cogs", "expense", "spend"),
    "quantity": ("quantity", "qty", "units", "volume", "demand"),
    "price": ("price", "rate", "unit price"),
    "customer": ("customer", "client", "buyer", "account"),
    "product": ("product", "sku", "item", "brand"),
    "category": ("category", "department", "segment", "type"),
    "region": ("region", "market", "state", "country", "city", "territory", "location"),
    "channel": ("channel", "source", "campaign", "platform"),
    "target/outcome": ("target", "label", "outcome", "churn", "converted", "status"),
}

@dataclass
class SemanticField:
    column: str
    semantic_role: str
    confidence: float
    reason: str

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

class SemanticSchemaEngine:
    def infer(self, df: pd.DataFrame, corrections: dict | None = None) -> list[SemanticField]:
        corrections = corrections or {}
        fields = []
        for column in df.columns:
            series, label = df[column], _name(column)
            if column in corrections:
                fields.append(SemanticField(column, corrections[column], 1.0, "User-confirmed workspace definition")); continue
            numeric = pd.to_numeric(series, errors="coerce").notna().mean()
            dates = parse_business_dates(series).notna().mean() if series.dtype == object else 0
            uniqueness = series.nunique(dropna=True) / max(len(series), 1)
            matches = [(role, term) for role, terms in ROLE_TERMS.items() for term in terms if term in label]
            if matches:
                role, term = matches[0]; confidence = .88
                reason = f"Column name contains '{term}'"
            elif dates >= .8:
                role, confidence, reason = "date/time", .82, "At least 80% of values parse as dates"
            elif uniqueness >= .98 and series.nunique() > 5:
                role, confidence, reason = "identifier", .72, "Nearly unique values suggest a record identifier"
            elif numeric >= .8:
                role, confidence, reason = "generic numerical", .66, "At least 80% of values parse as numeric"
            else:
                role, confidence, reason = "generic categorical", .62, "Non-numeric values without a business-name match"
            fields.append(SemanticField(column, role, confidence, reason))
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
    def __init__(self): self.schema=SemanticSchemaEngine(); self.kpis=KPIEngine(); self.planner=AnalyticsPlanner(); self.visuals=VisualizationEngine(); self.anomalies=AnomalyEngine(); self.ml=AutoMLEngine()
    def inspect(self, df, dataset_id="active", corrections=None):
        fields=self.schema.infer(df, corrections); anomaly=self.anomalies.investigate(df, fields, dataset_id)
        return {"profile":self.schema.profile(df),"semantic_schema":[asdict(f) for f in fields],"kpis":self.kpis.discover(df,fields),"visualizations":self.visuals.recommend(fields),"anomaly_evidence":asdict(anomaly) if anomaly else None}
    def answer(self, question, df, dataset_id="active"):
        fields=self.schema.infer(df); plan=self.planner.plan(question,fields); roles={f.semantic_role:f.column for f in fields}; q=question.lower()
        if not any(x in q for x in ("sales","revenue","profit","margin","customer","record","trend","anomaly","top","lowest","region","category")):
            return {"status":"INSUFFICIENT DATA","answer":"INSUFFICIENT DATA: no supported analytical objective could be resolved.","plan":plan,"evidence":[]}
        if "revenue" in roles: col=roles["revenue"]
        elif "profit" in roles: col=roles["profit"]
        else: return {"status":"INSUFFICIENT DATA","answer":"INSUFFICIENT DATA: a required business measure is unavailable.","plan":plan,"evidence":[]}
        values=pd.to_numeric(df[col],errors="coerce"); result={"measure":col,"sum":float(values.sum()),"mean":float(values.mean()),"rows":int(len(df))}; columns=[col]
        dimension = roles.get("region") if "region" in q else roles.get("category") if "category" in q else roles.get("region") or roles.get("category")
        if dimension and any(x in q for x in ("region","category","top","lowest","by ")):
            wants_lowest = any(x in q for x in ("lowest", "least", "bottom", "minimum", "min "))
            grouped=df.assign(_aura_value=values).groupby(dimension)["_aura_value"].sum().sort_values(ascending=wants_lowest)
            result["grouped_by"]=dimension; result["ranking"]={str(k):float(v) for k,v in grouped.head(10).items()}; columns.append(dimension)
            if not grouped.empty:
                result["requested_result"] = {"direction": "lowest" if wants_lowest else "highest", "dimension": str(grouped.index[0]), "value": float(grouped.iloc[0])}
        evidence=AnalyticsEvidence.create(dataset_id,plan["analytical_task"],columns,"pandas deterministic aggregation",result,uncertainty={"causal_claim":False})
        text=f"Verified result: {col} totals {result['sum']:,.2f} across {result['rows']:,} rows."
        if "requested_result" in result:
            item = result["requested_result"]
            text = f"Verified result: {item['dimension']} has the {item['direction']} {col} at {item['value']:,.2f}."
        elif "ranking" in result:
            text += f" Breakdown by {result['grouped_by']} is included in the evidence."
        return {"status":"OK","answer":text,"plan":plan,"evidence":[asdict(evidence)]}

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
