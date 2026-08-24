"""Evidence-first services for heterogeneous business data."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4
import re
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


ROLE_TERMS = {
    "identifier": ("id", "uuid", "code", "number", "invoice", "order"),
    "date/time": ("date", "time", "month", "year", "timestamp"),
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
            dates = pd.to_datetime(series, errors="coerce").notna().mean() if series.dtype == object else 0
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

class AutoMLEngine:
    def infer_task(self, df, target):
        if target not in df: return "invalid"
        y=df[target]
        if pd.api.types.is_numeric_dtype(y) and y.nunique() > 12: return "regression"
        return "binary classification" if y.nunique() == 2 else "multiclass classification"
    def train(self, df, target):
        task=self.infer_task(df,target)
        if task == "invalid" or len(df)<12: raise ValueError("A valid target and at least 12 rows are required.")
        x=pd.get_dummies(df.drop(columns=[target]), dummy_na=True).replace([np.inf,-np.inf],np.nan).fillna(0); y=df[target]
        Xtr,Xte,ytr,yte=train_test_split(x,y,test_size=.25,random_state=42)
        model = RandomForestRegressor(n_estimators=80,random_state=42) if task=="regression" else RandomForestClassifier(n_estimators=80,random_state=42)
        model.fit(Xtr,ytr); pred=model.predict(Xte)
        metrics={"mae":float(mean_absolute_error(yte,pred)),"r2":float(r2_score(yte,pred))} if task=="regression" else {"accuracy":float(accuracy_score(yte,pred))}
        return {"task":task,"model":"RandomForest","metrics":metrics,"feature_importance":dict(sorted(zip(x.columns,model.feature_importances_),key=lambda z:z[1],reverse=True)[:10]),"causal_claim":False}

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
        dimension=roles.get("region") or roles.get("category")
        if dimension and any(x in q for x in ("region","category","top","lowest","by ")):
            grouped=df.assign(_aura_value=values).groupby(dimension)["_aura_value"].sum().sort_values(ascending="lowest" not in q)
            result["grouped_by"]=dimension; result["ranking"]={str(k):float(v) for k,v in grouped.head(10).items()}; columns.append(dimension)
        evidence=AnalyticsEvidence.create(dataset_id,plan["analytical_task"],columns,"pandas deterministic aggregation",result,uncertainty={"causal_claim":False})
        text=f"Verified result: {col} totals {result['sum']:,.2f} across {result['rows']:,} rows."
        if "ranking" in result: text += f" Breakdown by {result['grouped_by']} is included in evidence {evidence.evidence_id}."
        return {"status":"OK","answer":text,"plan":plan,"evidence":[asdict(evidence)]}
