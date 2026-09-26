"""Deterministic, heterogeneous synthetic AURABench data families."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .schema import BenchmarkDataset, BenchmarkGroundTruth, BenchmarkQuestion

FAMILIES = {
    "retail": ("transaction_code", "purchase_date", "gross_merchandise_value", "net_margin", "market", "product_line"),
    "finance": ("ledger_ref", "posting_day", "recognized_income", "operating_expense", "business_unit", "account_class"),
    "human_resources": ("employee_ref", "review_month", "compensation_cost", "performance_score", "office_zone", "job_family"),
    "supply_chain": ("shipment_key", "dispatch_timestamp", "freight_spend", "units_shipped", "distribution_hub", "material_group"),
    "marketing": ("campaign_key", "event_date", "attributed_revenue", "media_spend", "audience_market", "campaign_type"),
    "ecommerce": ("checkout_token", "ordered_at", "basket_value", "contribution_profit", "delivery_region", "catalog_vertical"),
    "manufacturing": ("work_order", "production_date", "realized_value", "plant_cost", "factory_site", "product_family"),
    "energy": ("meter_reading_id", "reading_date", "billing_amount", "generation_cost", "service_area", "energy_source"),
}

def _roles(columns, family):
    identifier, date, value, secondary, region, category = columns
    secondary_role = "quantity" if family == "supply_chain" else ("generic numerical" if family == "human_resources" else ("profit" if family in {"retail", "ecommerce"} else "cost"))
    category_role = "product" if family == "retail" else "category"
    value_role = "cost" if family in {"human_resources", "supply_chain"} else "revenue"
    return {identifier:"identifier", date:"date/time", value:value_role, secondary:secondary_role, region:"region", category:category_role}

def generate_family(family: str, seed: int = 42, rows: int = 80) -> BenchmarkDataset:
    """Generate a family and ground truth; identical inputs produce identical data."""
    if family not in FAMILIES: raise ValueError(f"Unknown AURABench family: {family}")
    if rows < 12: raise ValueError("AURABench datasets require at least 12 rows.")
    rng=np.random.default_rng(seed); identifier,date,value,secondary,region,category=FAMILIES[family]
    dates=pd.date_range("2024-01-01",periods=rows,freq="D")
    regions=rng.choice(["North","South","East","West"],rows); categories=rng.choice(["Core","Premium","Value"],rows); volume=rng.integers(1,15,rows)
    base=180 + volume*35 + (regions=="North")*22 + (categories=="Premium")*55
    revenue=np.maximum(10,base+rng.normal(0,18,rows)).round(2); cost=np.maximum(1,revenue*rng.uniform(.35,.72,rows)+rng.normal(0,5,rows)).round(2)
    anomaly_index=rows-1; revenue[anomaly_index]=round(float(revenue[anomaly_index]*3.2),2)
    secondary_values=volume if family=="supply_chain" else cost
    if family=="human_resources": secondary_values=np.clip(2.5+(revenue/revenue.mean())+rng.normal(0,.25,rows),1,5).round(2)
    frame=pd.DataFrame({identifier:[f"{family[:3].upper()}-{seed}-{i:05d}" for i in range(rows)],date:dates,value:revenue,secondary:secondary_values,region:regions,category:categories})
    value_kpi = "Revenue" if _roles(FAMILIES[family],family)[value] == "revenue" else "Records"
    gt=BenchmarkGroundTruth(_roles(FAMILIES[family],family),list(dict.fromkeys([value_kpi,"Records"])),[
        BenchmarkQuestion(f"What is {value} by {region}?","ranking",[value,region]),
        BenchmarkQuestion(f"Show the trend of {value} over time","time trends",[value,date]),
        BenchmarkQuestion("What is employee morale?","unsupported",[],"INSUFFICIENT DATA"),
    ],[anomaly_index])
    return BenchmarkDataset(family,seed,frame,gt,{"rows":rows,"anomaly_injected":"high revenue record"})

def retail_bundle(seed: int = 42, rows: int = 80) -> BenchmarkDataset: return generate_family("retail",seed,rows)
def retail(seed: int = 42, rows: int = 80) -> pd.DataFrame: return retail_bundle(seed,rows).frame
def all_families(seed: int = 42, rows: int = 80) -> list[BenchmarkDataset]: return [generate_family(family,seed,rows) for family in FAMILIES]
