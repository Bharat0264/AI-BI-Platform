import sys
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask
from flask import Response
from flask import jsonify
from flask import request
from flask import send_file
from flask import send_from_directory

ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from prediction import predict_sales
from report_generator import generate_pdf_report
from schema_engine import normalize_business_dataset
from stock_analysis import analyze_stock
from platform_store import add_record, delete_record, get_record, get_setting, init_store, list_records, set_setting, update_record
from aura import AuraOrchestrator
from aura.providers import GeminiEvidenceProvider
from persistence import AuraRepository
from persistence.mongo import ping_database


app = Flask(__name__, static_folder="frontend", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 24 * 1024 * 1024
init_store()

DATA_PATH = ROOT_DIR / "data" / "Sample - Superstore.csv"
SESSION_DATA_PATH = ROOT_DIR / "data" / ".active_dataset.pkl"
SESSION_META_PATH = ROOT_DIR / "data" / ".active_dataset_source.txt"
ACTIVE_DATASET = {"df": None, "source": None}
AURA = AuraOrchestrator()
PERSISTENCE = AuraRepository()
REQUIRED_COLUMNS = [
    "Order ID",
    "Order Date",
    "Region",
    "Category",
    "Sales",
    "Profit",
    "Discount",
]


def persist_active_dataset(df=None, source=None):
    if df is None:
        SESSION_DATA_PATH.unlink(missing_ok=True)
        SESSION_META_PATH.unlink(missing_ok=True)
        return
    df.to_pickle(SESSION_DATA_PATH)
    SESSION_META_PATH.write_text(str(source or "Saved dataset"), encoding="utf-8")


def aura_context(df, source):
    """Resolve normalized persistence ownership without changing route contracts."""
    workspace_id = PERSISTENCE.workspace(get_setting("current_user", {}).get("workspace", "Executive Workspace"))
    dataset_id = PERSISTENCE.dataset(workspace_id, str(source or "active"), df, SESSION_DATA_PATH)
    return workspace_id, dataset_id


def restore_active_dataset():
    if SESSION_DATA_PATH.exists():
        try:
            ACTIVE_DATASET["df"] = pd.read_pickle(SESSION_DATA_PATH)
            ACTIVE_DATASET["source"] = SESSION_META_PATH.read_text(encoding="utf-8") if SESSION_META_PATH.exists() else "Saved dataset"
        except Exception:
            app.logger.exception("Could not restore the saved local dataset")


restore_active_dataset()


def read_dataset(source, filename=None):
    name = (filename or getattr(source, "filename", "") or str(source)).lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(source)
    if name.endswith(".json"):
        return pd.read_json(source)
    try:
        return pd.read_csv(source, encoding="utf-8")
    except UnicodeDecodeError:
        if hasattr(source, "seek"):
            source.seek(0)
        return pd.read_csv(source, encoding="latin1")


def validate_dataset(df):
    return [column for column in REQUIRED_COLUMNS if column not in df.columns]


def prepare_dataset(df):
    prepared, _, _ = normalize_business_dataset(df)
    prepared["Order Date"] = pd.to_datetime(prepared["Order Date"], errors="coerce")
    prepared["Sales"] = pd.to_numeric(prepared["Sales"], errors="coerce").fillna(0)
    prepared["Profit"] = pd.to_numeric(prepared["Profit"], errors="coerce").fillna(0)
    prepared["Discount"] = pd.to_numeric(prepared["Discount"], errors="coerce").fillna(0)
    prepared["Quantity"] = pd.to_numeric(prepared.get("Quantity", 1), errors="coerce").fillna(0)
    if "Inventory" in prepared.columns:
        prepared["Inventory"] = pd.to_numeric(prepared["Inventory"], errors="coerce").fillna(0)
    return prepared.dropna(subset=["Order Date"])


def money(value):
    return f"${value:,.0f}"


def number(value):
    return f"{value:,.0f}"


def percent(value):
    if pd.isna(value):
        return "0%"
    return f"{value:.0%}"


def signed_percent(value):
    if pd.isna(value):
        return "0%"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.0%}"


def safe_column(df, column, fallback="Unknown"):
    if column in df.columns:
        return df[column].fillna(fallback).astype(str)
    return pd.Series([fallback] * len(df), index=df.index)


def safe_nunique(df, column):
    return int(df[column].nunique()) if column in df.columns else 0


def change_ratio(current, previous):
    if previous == 0:
        return 0
    return (current - previous) / abs(previous)


def dataset_from_request():
    uploaded = request.files.get("dataset")
    if uploaded and uploaded.filename:
        return read_dataset(uploaded, uploaded.filename), uploaded.filename
    if ACTIVE_DATASET["df"] is not None:
        return ACTIVE_DATASET["df"].copy(), ACTIVE_DATASET["source"]
    return None, None


def empty_payload():
    return {
        "empty": True,
        "source": "No CSV imported",
        "rows": 0,
        "regions": [],
        "categories": [],
        "selectedRegions": [],
        "selectedCategories": [],
        "metrics": [],
        "quality": {
            "score": "N/A",
            "rows": 0,
            "cleanRows": 0,
            "columns": 0,
            "missingCells": 0,
            "duplicateRows": 0,
            "invalidDates": 0,
            "missingRequired": [],
        },
        "charts": {
            "categorySales": {"labels": [], "values": []},
            "regionProfit": {"labels": [], "values": []},
            "monthlySales": {"labels": [], "values": []},
            "marginByCategory": {"labels": [], "values": []},
            "discountByCategory": {"labels": [], "values": []},
            "forecast": {
                "historyLabels": [],
                "historyValues": [],
                "labels": [],
                "values": [],
                "lower": [],
                "upper": [],
            },
        },
        "insights": [],
        "anomalies": [],
        "executiveSummary": [],
        "datasetProfile": {},
        "riskOverview": {},
        "segmentTable": [],
        "productTable": [],
        "marginMatrix": [],
        "discountSensitivity": [],
        "opportunities": [],
        "forecastTable": [],
        "demandPlan": {"totals": {}, "products": [], "sectors": [], "quantityIsEstimated": False},
        "preview": [],
    }


def filter_dataset(df, payload=None):
    payload = payload or request.args
    selected_regions = payload.getlist("region") if hasattr(payload, "getlist") else payload.get("regions", [])
    selected_categories = payload.getlist("category") if hasattr(payload, "getlist") else payload.get("categories", [])

    regions = sorted(df["Region"].dropna().astype(str).unique())
    categories = sorted(df["Category"].dropna().astype(str).unique())

    if not selected_regions:
        selected_regions = regions
    if not selected_categories:
        selected_categories = categories

    filtered = df[
        df["Region"].astype(str).isin(selected_regions)
        & df["Category"].astype(str).isin(selected_categories)
    ].copy()
    return filtered, regions, categories, selected_regions, selected_categories


def kpis(df):
    total_sales = df["Sales"].sum()
    total_profit = df["Profit"].sum()
    total_orders = df["Order ID"].nunique()
    avg_discount = df["Discount"].mean()
    profit_margin = total_profit / total_sales if total_sales else 0
    current, previous = period_performance(df)
    sales_delta = change_ratio(current["sales"], previous["sales"])
    profit_delta = change_ratio(current["profit"], previous["profit"])
    return [
        {"label": "Total Sales", "value": money(total_sales), "note": f"{signed_percent(sales_delta)} vs previous period", "tone": tone_for_delta(sales_delta)},
        {"label": "Total Profit", "value": money(total_profit), "note": f"{signed_percent(profit_delta)} vs previous period", "tone": tone_for_delta(profit_delta)},
        {"label": "Orders", "value": f"{total_orders:,}", "note": "Unique customer orders", "tone": "neutral"},
        {"label": "Avg Discount", "value": percent(avg_discount), "note": "Average discount rate", "tone": "warn" if avg_discount >= 0.2 else "good"},
        {"label": "Profit Margin", "value": percent(profit_margin), "note": "Profit as a share of sales", "tone": "good" if profit_margin >= 0.12 else "warn" if profit_margin >= 0.04 else "bad"},
    ]


def tone_for_delta(value):
    if value >= 0.05:
        return "good"
    if value <= -0.05:
        return "bad"
    return "neutral"


def period_performance(df):
    if df.empty:
        return {"sales": 0, "profit": 0, "orders": 0}, {"sales": 0, "profit": 0, "orders": 0}
    last_date = df["Order Date"].max()
    current_start = last_date - pd.DateOffset(months=6)
    previous_start = current_start - pd.DateOffset(months=6)
    current_df = df[df["Order Date"] > current_start]
    previous_df = df[(df["Order Date"] > previous_start) & (df["Order Date"] <= current_start)]
    return period_totals(current_df), period_totals(previous_df)


def period_totals(df):
    return {
        "sales": float(df["Sales"].sum()),
        "profit": float(df["Profit"].sum()),
        "orders": int(df["Order ID"].nunique()) if "Order ID" in df.columns else int(len(df)),
    }


def dataset_profile(raw_df, prepared_df, filtered, source_name):
    numeric_cols = raw_df.select_dtypes(include="number").columns.tolist()
    start = prepared_df["Order Date"].min()
    end = prepared_df["Order Date"].max()
    return {
        "source": source_name,
        "dateRange": f"{start.date()} to {end.date()}" if pd.notna(start) and pd.notna(end) else "Unknown",
        "recordsAnalyzed": int(len(filtered)),
        "totalRecords": int(len(raw_df)),
        "columns": int(len(raw_df.columns)),
        "numericColumns": len(numeric_cols),
        "regions": safe_nunique(prepared_df, "Region"),
        "categories": safe_nunique(prepared_df, "Category"),
        "customers": safe_nunique(prepared_df, "Customer Name"),
        "products": safe_nunique(prepared_df, "Product Name"),
    }


def quality_scan(raw_df, prepared_df):
    missing_required = validate_dataset(raw_df)
    invalid_dates = pd.to_datetime(raw_df.get("Order Date"), errors="coerce").isna().sum()
    missing_cells = int(raw_df.isna().sum().sum())
    duplicate_rows = int(raw_df.duplicated().sum())
    score = 100
    score -= min(30, len(missing_required) * 12)
    score -= min(20, missing_cells // max(len(raw_df), 1))
    score -= min(20, int(invalid_dates))
    score -= min(15, duplicate_rows)
    return {
        "score": max(score, 0),
        "rows": len(raw_df),
        "cleanRows": len(prepared_df),
        "columns": len(raw_df.columns),
        "missingCells": missing_cells,
        "duplicateRows": duplicate_rows,
        "invalidDates": int(invalid_dates),
        "missingRequired": missing_required,
    }


def recommendations(df):
    total_sales = df["Sales"].sum()
    total_profit = df["Profit"].sum()
    margin = total_profit / total_sales if total_sales else 0
    avg_discount = df["Discount"].mean()
    category_sales = df.groupby("Category")["Sales"].sum().sort_values(ascending=False)
    region_profit = df.groupby("Region")["Profit"].sum().sort_values()
    loss_count = int((df["Profit"] < 0).sum())
    top_category = category_sales.index[0] if not category_sales.empty else "N/A"
    weakest_region = region_profit.index[0] if not region_profit.empty else "N/A"
    strongest_region = region_profit.index[-1] if not region_profit.empty else "N/A"
    return [
        {"title": "Revenue opportunity", "body": f"{top_category} is the strongest category. Build campaigns and bundles around it."},
        {"title": "Profit leak", "body": f"{loss_count:,} transactions are loss-making. Review discounts, shipping cost, and product mix."},
        {"title": "Regional risk", "body": f"{weakest_region} has the weakest profit contribution while {strongest_region} leads performance."},
        {"title": "Pricing pressure", "body": f"Average discount is {percent(avg_discount)}. Keep discounts below margin-protecting thresholds."},
        {"title": "Executive action", "body": f"Current margin is {percent(margin)}. Prioritize high-margin categories before chasing pure revenue growth."},
    ]


def executive_summary(df):
    total_sales = df["Sales"].sum()
    total_profit = df["Profit"].sum()
    margin = total_profit / total_sales if total_sales else 0
    current, previous = period_performance(df)
    sales_delta = change_ratio(current["sales"], previous["sales"])
    profit_delta = change_ratio(current["profit"], previous["profit"])
    loss_rate = float((df["Profit"] < 0).mean()) if len(df) else 0
    discount = float(df["Discount"].mean()) if len(df) else 0
    top_region = df.groupby("Region")["Profit"].sum().sort_values(ascending=False)
    region = top_region.index[0] if not top_region.empty else "N/A"
    return [
        {"label": "Growth posture", "value": "Expanding" if sales_delta >= 0.05 else "Stable" if sales_delta > -0.05 else "Contracting", "detail": f"Sales are {signed_percent(sales_delta)} compared with the prior six-month period."},
        {"label": "Profit quality", "value": "Healthy" if margin >= 0.12 else "Watchlist" if margin >= 0.04 else "Critical", "detail": f"Profit margin is {percent(margin)} with profit momentum at {signed_percent(profit_delta)}."},
        {"label": "Risk exposure", "value": "Elevated" if loss_rate >= 0.2 or discount >= 0.25 else "Moderate" if loss_rate >= 0.1 or discount >= 0.15 else "Controlled", "detail": f"{percent(loss_rate)} of transactions lose money and average discount is {percent(discount)}."},
        {"label": "Best operating zone", "value": str(region), "detail": "This region contributes the strongest absolute profit in the selected dataset."},
    ]


def anomalies(df):
    items = []
    losses = df[df["Profit"] < 0]
    if not losses.empty:
        worst = losses.sort_values("Profit").iloc[0]
        items.append({"title": "Largest loss", "severity": "high", "body": f"{worst.get('Category', 'Unknown')} in {worst.get('Region', 'Unknown')} lost {money(abs(worst['Profit']))}."})
    high_discount = df[df["Discount"] >= 0.5]
    if not high_discount.empty:
        items.append({"title": "High discounts", "severity": "medium", "body": f"{len(high_discount):,} rows have discounts of 50% or more."})
    if "Sub-Category" in df.columns:
        subcat = df.groupby("Sub-Category").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum")).reset_index()
        subcat["Margin"] = np.where(subcat["Sales"] > 0, subcat["Profit"] / subcat["Sales"], 0)
        weak = subcat[(subcat["Sales"] > subcat["Sales"].median()) & (subcat["Margin"] < 0)].sort_values("Profit")
        if not weak.empty:
            row = weak.iloc[0]
            items.append({"title": "Revenue with negative margin", "severity": "high", "body": f"{row['Sub-Category']} generates {money(row['Sales'])} in sales but loses {money(abs(row['Profit']))}."})
    if not items:
        items.append({"title": "No major anomaly", "severity": "low", "body": "No extreme losses or discount spikes were detected."})
    return items


def group_records(df, group_col, value_col):
    data = df.groupby(group_col)[value_col].sum().reset_index()
    return data[group_col].astype(str).tolist(), data[value_col].round(2).tolist()


def margin_records(df, group_col):
    data = df.groupby(group_col).agg(Sales=("Sales", "sum"), Profit=("Profit", "sum")).reset_index()
    data["Margin"] = np.where(data["Sales"] > 0, data["Profit"] / data["Sales"], 0)
    data = data.sort_values("Margin", ascending=False)
    return data[group_col].astype(str).tolist(), data["Margin"].round(4).tolist()


def average_records(df, group_col, value_col):
    data = df.groupby(group_col)[value_col].mean().reset_index().sort_values(value_col, ascending=False)
    return data[group_col].astype(str).tolist(), data[value_col].round(4).tolist()


def monthly_records(df):
    data = (
        df.groupby(df["Order Date"].dt.to_period("M"))["Sales"]
        .sum()
        .reset_index()
        .sort_values("Order Date")
    )
    data["Order Date"] = data["Order Date"].astype(str)
    return data["Order Date"].tolist(), data["Sales"].round(2).tolist()


def leaderboard(df, group_col, limit=8):
    labels = safe_column(df, group_col)
    grouped = (
        df.assign(_label=labels)
        .groupby("_label")
        .agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"), Orders=("Order ID", "nunique"), Discount=("Discount", "mean"))
        .reset_index()
    )
    grouped["Margin"] = np.where(grouped["Sales"] > 0, grouped["Profit"] / grouped["Sales"], 0)
    grouped = grouped.sort_values(["Profit", "Sales"], ascending=False).head(limit)
    return [
        {
            "name": row["_label"],
            "sales": money(row["Sales"]),
            "profit": money(row["Profit"]),
            "orders": number(row["Orders"]),
            "margin": percent(row["Margin"]),
            "discount": percent(row["Discount"]),
        }
        for _, row in grouped.iterrows()
    ]


def margin_risk_matrix(df):
    grouped = (
        df.assign(Category=safe_column(df, "Category"), Region=safe_column(df, "Region"))
        .groupby(["Region", "Category"])
        .agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"), Orders=("Order ID", "nunique"), AvgDiscount=("Discount", "mean"), LossRows=("Profit", lambda values: int((values < 0).sum())))
        .reset_index()
    )
    grouped["Margin"] = np.where(grouped["Sales"] > 0, grouped["Profit"] / grouped["Sales"], 0)
    grouped["LossRate"] = np.where(grouped["Orders"] > 0, grouped["LossRows"] / grouped["Orders"], 0)
    grouped["RiskScore"] = (
        np.maximum(0, 0.16 - grouped["Margin"]) * 220
        + grouped["AvgDiscount"] * 65
        + grouped["LossRate"] * 45
    ).clip(0, 100)
    grouped = grouped.sort_values("RiskScore", ascending=False).head(10)
    return [
        {
            "region": row["Region"],
            "category": row["Category"],
            "sales": money(row["Sales"]),
            "profit": money(row["Profit"]),
            "margin": percent(row["Margin"]),
            "discount": percent(row["AvgDiscount"]),
            "riskScore": int(round(row["RiskScore"])),
            "risk": "High" if row["RiskScore"] >= 60 else "Medium" if row["RiskScore"] >= 35 else "Low",
        }
        for _, row in grouped.iterrows()
    ]


def discount_sensitivity(df):
    bins = [-0.01, 0.05, 0.15, 0.30, 0.50, 1.0]
    labels = ["0-5%", "5-15%", "15-30%", "30-50%", "50%+"]
    data = df.copy()
    data["Discount Band"] = pd.cut(data["Discount"], bins=bins, labels=labels)
    grouped = (
        data.groupby("Discount Band", observed=False)
        .agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"), Orders=("Order ID", "nunique"))
        .reset_index()
    )
    grouped["Margin"] = np.where(grouped["Sales"] > 0, grouped["Profit"] / grouped["Sales"], 0)
    return [
        {
            "band": str(row["Discount Band"]),
            "sales": money(row["Sales"]),
            "profit": money(row["Profit"]),
            "orders": number(row["Orders"]),
            "margin": percent(row["Margin"]),
        }
        for _, row in grouped.iterrows()
    ]


def opportunity_map(df):
    group_col = "Sub-Category" if "Sub-Category" in df.columns else "Category"
    grouped = df.assign(_label=safe_column(df, group_col)).groupby("_label").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"), Discount=("Discount", "mean")).reset_index()
    grouped["Margin"] = np.where(grouped["Sales"] > 0, grouped["Profit"] / grouped["Sales"], 0)
    sales_q3 = grouped["Sales"].quantile(0.75)
    high_sales_low_margin = grouped[(grouped["Sales"] >= sales_q3) & (grouped["Margin"] < grouped["Margin"].median())].sort_values("Sales", ascending=False).head(3)
    high_margin_under_scaled = grouped[(grouped["Margin"] >= grouped["Margin"].quantile(0.75)) & (grouped["Sales"] < sales_q3)].sort_values("Margin", ascending=False).head(3)
    opportunities = []
    for _, row in high_sales_low_margin.iterrows():
        opportunities.append({"title": row["_label"], "type": "Margin recovery", "body": f"High sales at {money(row['Sales'])}, but margin is only {percent(row['Margin'])}. Tighten discounting and cost controls."})
    for _, row in high_margin_under_scaled.iterrows():
        opportunities.append({"title": row["_label"], "type": "Growth bet", "body": f"Margin is strong at {percent(row['Margin'])}; increase visibility to scale profitable demand."})
    return opportunities[:6]


def risk_overview(df):
    total_sales = df["Sales"].sum()
    profit = df["Profit"].sum()
    margin = profit / total_sales if total_sales else 0
    loss_rate = float((df["Profit"] < 0).mean()) if len(df) else 0
    avg_discount = float(df["Discount"].mean()) if len(df) else 0
    score = int(np.clip((0.18 - margin) * 180 + loss_rate * 45 + avg_discount * 55, 0, 100))
    return {
        "score": score,
        "level": "High" if score >= 60 else "Medium" if score >= 35 else "Low",
        "margin": percent(margin),
        "lossRate": percent(loss_rate),
        "avgDiscount": percent(avg_discount),
        "levers": [
            {"label": "Reduce loss-making rows", "impact": money(abs(df.loc[df["Profit"] < 0, "Profit"].sum()))},
            {"label": "Recover 5% sales from discount leakage", "impact": money(total_sales * avg_discount * 0.05)},
            {"label": "Lift margin by 2 points", "impact": money(total_sales * 0.02)},
        ],
    }


def demand_plan(df, quantity_is_estimated=False):
    """Forecast next-month product demand and translate it into inventory actions."""
    product_col = "Product Name" if "Product Name" in df.columns else "Category"
    data = df.copy()
    data[product_col] = safe_column(data, product_col, "Unknown product")
    data["Quantity"] = pd.to_numeric(data.get("Quantity", 1), errors="coerce").fillna(0).clip(lower=0)
    data["Month"] = data["Order Date"].dt.to_period("M")
    last_month = data["Month"].max()
    next_month = str(last_month + 1)
    plans = []
    # Detailed SKU planning is capped to the most commercially material items so
    # large catalogues remain interactive. Sector totals cover those priority SKUs.
    priority_products = data.groupby(product_col)["Sales"].sum().nlargest(200).index
    planning_data = data[data[product_col].isin(priority_products)]
    for product, rows in planning_data.groupby(product_col):
        monthly = rows.groupby("Month").agg(Units=("Quantity", "sum"), Revenue=("Sales", "sum"), Profit=("Profit", "sum")).sort_index()
        if monthly.empty:
            continue
        full_index = pd.period_range(monthly.index.min(), last_month, freq="M")
        units = monthly["Units"].reindex(full_index, fill_value=0).astype(float)
        recent = units.tail(min(6, len(units)))
        if len(recent) >= 2:
            slope = float(np.polyfit(np.arange(len(recent)), recent.values, 1)[0])
            baseline = float(recent.tail(min(3, len(recent))).mean())
            predicted_units = max(0, baseline + slope * 0.55)
        else:
            slope, predicted_units = 0.0, float(recent.iloc[-1])
        variability = float(recent.std(ddof=0)) if len(recent) > 1 else predicted_units * 0.15
        safety_stock = max(0, 1.28 * variability)
        recommended_stock = int(np.ceil(predicted_units + safety_stock))
        current_stock = float(rows["Inventory"].iloc[-1]) if "Inventory" in rows.columns else 0.0
        stock_to_add = max(0, int(np.ceil(recommended_stock - current_stock)))
        total_units = float(rows["Quantity"].sum())
        revenue_per_unit = float(rows["Sales"].sum()) / total_units if total_units else 0
        profit_per_unit = float(rows["Profit"].sum()) / total_units if total_units else 0
        growth = slope / max(float(recent.mean()), 1)
        history_score = min(1, len(units) / 12)
        noise = variability / max(float(recent.mean()), 1)
        confidence = int(np.clip(45 + history_score * 40 - noise * 25, 25, 92))
        category = str(rows["Category"].mode().iloc[0]) if "Category" in rows and not rows["Category"].mode().empty else "Uncategorized"
        plans.append({
            "product": str(product), "sector": category, "forecastMonth": next_month,
            "predictedUnits": int(round(predicted_units)), "safetyStock": int(np.ceil(safety_stock)),
            "recommendedStock": recommended_stock, "currentStock": int(round(current_stock)),
            "stockToAdd": stock_to_add, "predictedRevenue": round(predicted_units * revenue_per_unit, 2),
            "predictedProfit": round(predicted_units * profit_per_unit, 2), "growthRate": round(growth * 100, 1),
            "confidence": confidence,
            "action": "Increase production" if growth >= 0.03 else "Reduce production" if growth <= -0.08 else "Maintain production",
            "stockBasis": "current inventory supplied" if "Inventory" in rows.columns else "no current inventory supplied",
        })
    plans.sort(key=lambda item: (item["action"] == "Increase production", item["growthRate"], item["predictedRevenue"]), reverse=True)
    sector_rows = []
    for sector in sorted({item["sector"] for item in plans}):
        items = [item for item in plans if item["sector"] == sector]
        sector_rows.append({
            "sector": sector, "stockToAdd": sum(i["stockToAdd"] for i in items),
            "predictedRevenue": round(sum(i["predictedRevenue"] for i in items), 2),
            "predictedProfit": round(sum(i["predictedProfit"] for i in items), 2),
            "growthRate": round(np.average([i["growthRate"] for i in items], weights=[max(i["predictedRevenue"], 1) for i in items]), 1),
        })
    sector_rows.sort(key=lambda item: item["growthRate"], reverse=True)
    totals = {
        "forecastMonth": next_month, "predictedUnits": sum(i["predictedUnits"] for i in plans),
        "stockToAdd": sum(i["stockToAdd"] for i in plans), "predictedRevenue": round(sum(i["predictedRevenue"] for i in plans), 2),
        "predictedProfit": round(sum(i["predictedProfit"] for i in plans), 2),
    }
    return {"totals": totals, "products": plans[:50], "sectors": sector_rows, "quantityIsEstimated": quantity_is_estimated}


def analysis_payload(raw_df, source_name, payload=None):
    try:
        raw_df, column_mapping, schema_warnings = normalize_business_dataset(raw_df)
    except ValueError as exc:
        return {"error": str(exc)}, 400

    df = prepare_dataset(raw_df)
    df.attrs["column_mapping"] = column_mapping
    if df.empty:
        return {"error": "No valid dated rows were found in the dataset."}, 400

    filtered, regions, categories, selected_regions, selected_categories = filter_dataset(df, payload)
    if filtered.empty:
        return {"error": "No rows match the selected filters."}, 400

    category_labels, category_values = group_records(filtered, "Category", "Sales")
    region_labels, region_values = group_records(filtered, "Region", "Profit")
    margin_labels, margin_values = margin_records(filtered, "Category")
    discount_labels, discount_values = average_records(filtered, "Category", "Discount")
    month_labels, month_values = monthly_records(filtered)
    monthly_sales, forecast = predict_sales(filtered.copy())
    forecast_margin = float(filtered["Profit"].sum() / filtered["Sales"].sum()) if filtered["Sales"].sum() else 0
    if not forecast.empty:
        forecast["Predicted Revenue"] = forecast["Predicted Sales"]
        forecast["Predicted Profit"] = forecast["Predicted Revenue"] * forecast_margin

    return {
        "source": source_name,
        "rows": int(len(filtered)),
        "regions": regions,
        "categories": categories,
        "selectedRegions": selected_regions,
        "selectedCategories": selected_categories,
        "metrics": kpis(filtered),
        "quality": quality_scan(raw_df, df),
        "datasetProfile": {**dataset_profile(raw_df, df, filtered, source_name), "columnMapping": column_mapping, "schemaWarnings": schema_warnings},
        "executiveSummary": executive_summary(filtered),
        "riskOverview": risk_overview(filtered),
        "charts": {
            "categorySales": {"labels": category_labels, "values": category_values},
            "regionProfit": {"labels": region_labels, "values": region_values},
            "monthlySales": {"labels": month_labels, "values": month_values},
            "marginByCategory": {"labels": margin_labels, "values": margin_values},
            "discountByCategory": {"labels": discount_labels, "values": discount_values},
            "forecast": {
                "historyLabels": monthly_sales["Order Date"].astype(str).tolist(),
                "historyValues": monthly_sales["Sales"].round(2).tolist(),
                "labels": forecast["Forecast Month"].astype(str).tolist() if not forecast.empty else [],
                "values": forecast["Predicted Sales"].round(2).tolist() if not forecast.empty else [],
                "lower": forecast["Lower Bound"].round(2).tolist() if not forecast.empty else [],
                "upper": forecast["Upper Bound"].round(2).tolist() if not forecast.empty else [],
            },
        },
        "insights": recommendations(filtered),
        "anomalies": anomalies(filtered),
        "segmentTable": leaderboard(filtered, "Segment" if "Segment" in filtered.columns else "Category"),
        "productTable": leaderboard(filtered, "Product Name" if "Product Name" in filtered.columns else "Category"),
        "marginMatrix": margin_risk_matrix(filtered),
        "discountSensitivity": discount_sensitivity(filtered),
        "opportunities": opportunity_map(filtered),
        "forecastTable": forecast.round(2).to_dict(orient="records"),
        "demandPlan": demand_plan(filtered, "Quantity" not in column_mapping),
        "preview": filtered.head(25).fillna("").to_dict(orient="records"),
    }, 200


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def api_health():
    try:
        ping_database()
        return jsonify({"status": "ready", "persistence": "mongodb"})
    except Exception:
        return jsonify({"status": "not_ready", "persistence": "mongodb"}), 503


@app.route("/api/analysis", methods=["GET"])
def api_analysis():
    raw_df, source_name = dataset_from_request()
    if raw_df is None:
        return jsonify(empty_payload())
    payload, status = analysis_payload(raw_df, source_name)
    return jsonify(payload), status


@app.route("/api/reset", methods=["POST"])
def api_reset():
    ACTIVE_DATASET["df"] = None
    ACTIVE_DATASET["source"] = None
    persist_active_dataset()
    return jsonify(empty_payload())


@app.route("/api/upload", methods=["POST"])
def api_upload():
    uploaded = request.files.get("dataset")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Choose a CSV, Excel, or JSON file to import."}), 400
    if not uploaded.filename.lower().endswith((".csv", ".xlsx", ".xls", ".json")):
        return jsonify({"error": "Upload a CSV, Excel, or JSON business dataset."}), 400

    raw_df, source_name = read_dataset(uploaded, uploaded.filename), uploaded.filename
    payload, status = analysis_payload(raw_df, source_name)
    if status == 200:
        ACTIVE_DATASET["df"] = raw_df.copy()
        ACTIVE_DATASET["source"] = source_name
        persist_active_dataset(raw_df, source_name)
    return jsonify(payload), status


@app.route("/api/demo", methods=["POST"])
def api_demo():
    if not DATA_PATH.exists():
        return jsonify({"error": "Demo dataset is not available on this deployment."}), 404
    raw_df = read_dataset(DATA_PATH)
    payload, status = analysis_payload(raw_df, DATA_PATH.name)
    if status == 200:
        ACTIVE_DATASET["df"] = raw_df.copy()
        ACTIVE_DATASET["source"] = DATA_PATH.name
        persist_active_dataset(raw_df, DATA_PATH.name)
    return jsonify(payload), status


@app.route("/api/ask", methods=["POST"])
def api_ask():
    body = request.get_json(silent=True) or {}
    question = str(body.get("question", "")).strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    raw_df, _ = dataset_from_request()
    if raw_df is None:
        return jsonify({"error": "Import a CSV before asking AI questions."}), 400
    # AURA queries the original frame so unfamiliar, non-sales schemas remain analyzable.
    result = AURA.answer(question, raw_df, str(ACTIVE_DATASET.get("source") or "active"))
    narrative = None
    if result["status"] == "OK":
        narrative = GeminiEvidenceProvider().explain(question, result["evidence"])
        if narrative:
            result["answer"] = narrative
    workspace_id, dataset_id = aura_context(raw_df, ACTIVE_DATASET.get("source"))
    for item in result["evidence"]:
        PERSISTENCE.evidence(workspace_id, dataset_id, item)
    PERSISTENCE.query(workspace_id, dataset_id, question, result, "Gemini" if narrative else None)
    citations = [{"label": "AURA evidence", "value": item["evidence_id"], "source": item["method"]} for item in result["evidence"]]
    add_record("history", question[:80], {"type": "AURA verified question", "question": question, "answer": result["answer"][:500], "evidence": result["evidence"], "plan": result["plan"]})
    return jsonify({"answer": result["answer"], "citations": citations, "status": result["status"], "plan": result["plan"], "evidence": result["evidence"]})


@app.route("/api/aura/inspect")
def aura_inspect():
    raw_df, source = dataset_from_request()
    if raw_df is None:
        return jsonify({"error": "Import a dataset first."}), 400
    workspace_id, dataset_id = aura_context(raw_df, source)
    corrections = {**get_setting(f"aura_schema:{source}", {}), **PERSISTENCE.corrections(dataset_id)}
    inspection = AURA.inspect(raw_df, str(source), corrections)
    PERSISTENCE.save_inspection(dataset_id, inspection)
    return jsonify(inspection)


@app.route("/api/aura/schema", methods=["PUT"])
def aura_schema_corrections():
    raw_df, source = dataset_from_request()
    if raw_df is None:
        return jsonify({"error": "Import a dataset first."}), 400
    corrections = (request.get_json(silent=True) or {}).get("corrections", {})
    if not isinstance(corrections, dict) or any(c not in raw_df.columns for c in corrections):
        return jsonify({"error": "Corrections must map existing columns to roles."}), 400
    saved = {**get_setting(f"aura_schema:{source}", {}), **corrections}
    set_setting(f"aura_schema:{source}", saved)
    _, dataset_id = aura_context(raw_df, source)
    PERSISTENCE.correct_semantics(dataset_id, corrections)
    return jsonify({"saved": True, "semantic_schema": [field.__dict__ for field in AURA.schema.infer(raw_df, saved)]})


@app.route("/api/aura/ml", methods=["POST"])
def aura_ml():
    raw_df, source = dataset_from_request()
    target = str((request.get_json(silent=True) or {}).get("target", ""))
    if raw_df is None:
        return jsonify({"error": "Import a dataset first."}), 400
    try:
        run = AURA.ml.train(raw_df, target)
        workspace_id, dataset_id = aura_context(raw_df, source)
        PERSISTENCE.ml(workspace_id, dataset_id, target, run)
        add_record("ml_run", target, run)
        return jsonify(run)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/aura/analytics", methods=["POST"])
def aura_analytics():
    raw_df, source = dataset_from_request()
    body = request.get_json(silent=True) or {}
    if raw_df is None:
        return jsonify({"error": "Import a dataset first."}), 400
    try:
        run = AURA.run_analysis(str(body.get("objective", "descriptive statistics")), raw_df, str(source), body.get("dimension"), body.get("measure"))
        workspace_id, dataset_id = aura_context(raw_df, source)
        PERSISTENCE.analytics(workspace_id, dataset_id, str(body.get("objective", "Analytics")), run)
        add_record("analytics_run", str(body.get("objective", "Analytics"))[:80], run)
        return jsonify(run)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/aura/root-cause", methods=["POST"])
def aura_root_cause():
    raw_df, source = dataset_from_request()
    if raw_df is None:
        return jsonify({"error": "Import a dataset first."}), 400
    evidence, narrative = AURA.anomalies.root_cause(raw_df, AURA.schema.infer(raw_df), str(source))
    if not evidence:
        return jsonify({"status": "INSUFFICIENT DATA", "answer": narrative, "evidence": None})
    payload = evidence.__dict__
    workspace_id, dataset_id = aura_context(raw_df, source)
    PERSISTENCE.investigation(workspace_id, dataset_id, payload)
    add_record("anomaly_investigation", "Latest period investigation", {"answer": narrative, "evidence": payload})
    return jsonify({"status": "OK", "answer": narrative, "evidence": payload})


@app.route("/api/aura/history")
def aura_history():
    kinds = ["analytics_run", "ml_run", "anomaly_investigation", "history"]
    return jsonify({kind: list_records(kind)[:20] for kind in kinds})


@app.route("/api/stocks/analyze", methods=["POST"])
def api_stock_analysis():
    body = request.get_json(silent=True) or {}
    company = str(body.get("company", "")).strip()
    asset_type = str(body.get("assetType", "stocks")).strip().lower()
    if not company:
        return jsonify({"error": "Enter an Indian company name or NSE/BSE symbol."}), 400
    try:
        return jsonify(analyze_stock(company, asset_type))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception:
        app.logger.exception("Stock market data request failed")
        return jsonify({"error": "Live market data is temporarily unavailable. Please try again shortly."}), 503


@app.route("/api/export/filtered")
def export_filtered():
    raw_df, _ = dataset_from_request()
    if raw_df is None:
        return jsonify({"error": "Import a CSV before exporting data."}), 400
    df = prepare_dataset(raw_df)
    filtered, *_ = filter_dataset(df)
    return Response(
        filtered.to_csv(index=False).encode("utf-8"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=filtered_business_data.csv"},
    )


@app.route("/api/report")
def export_report():
    raw_df, _ = dataset_from_request()
    if raw_df is None:
        return jsonify({"error": "Import a CSV before generating a report."}), 400
    df = prepare_dataset(raw_df)
    filtered, *_ = filter_dataset(df)
    _, forecast = predict_sales(filtered.copy())
    metrics = {item["label"]: item["value"] for item in kpis(filtered)}
    summary = executive_summary(filtered)
    evidence_records = [r["payload"].get("evidence") for r in list_records("history")[:10] if r["payload"].get("evidence")]
    pdf_path = generate_pdf_report(
        "\n\n".join([f"{item['label']}: {item['detail']}" for item in summary]),
        metrics=metrics,
        insights=recommendations(filtered),
        anomalies=anomalies(filtered),
        forecast=forecast,
        evidence=evidence_records,
    )
    workspace_id, dataset_id = aura_context(raw_df, ACTIVE_DATASET.get("source"))
    evidence_ids = [item.get("evidence_id") for record in evidence_records for item in (record if isinstance(record, list) else [record]) if isinstance(item, dict) and item.get("evidence_id")]
    PERSISTENCE.report(workspace_id, dataset_id, evidence_ids, pdf_path)
    return send_file(pdf_path, as_attachment=True, download_name="AI_Business_Report.pdf")


def plain_metrics(df):
    sales = float(df["Sales"].sum())
    profit = float(df["Profit"].sum())
    return {
        "sales": sales,
        "profit": profit,
        "margin": profit / sales if sales else 0,
        "discount": float(df["Discount"].mean()) if len(df) else 0,
        "orders": int(df["Order ID"].nunique()),
        "rows": int(len(df)),
    }


def evidence_for_question(question, df):
    """Return compact, deterministic evidence alongside generative answers."""
    metrics = plain_metrics(df)
    evidence = [
        {"label": "Rows analyzed", "value": f"{metrics['rows']:,}", "source": "Filtered dataset"},
        {"label": "Total sales", "value": money(metrics["sales"]), "source": "SUM(Sales)"},
        {"label": "Total profit", "value": money(metrics["profit"]), "source": "SUM(Profit)"},
        {"label": "Profit margin", "value": percent(metrics["margin"]), "source": "SUM(Profit) / SUM(Sales)"},
    ]
    lowered = question.lower()
    if "region" in lowered:
        row = df.groupby("Region")["Profit"].sum().sort_values().reset_index().iloc[0]
        evidence.append({"label": "Lowest-profit region", "value": f"{row['Region']} ({money(row['Profit'])})", "source": "Profit grouped by Region"})
    if "category" in lowered:
        row = df.groupby("Category")["Sales"].sum().sort_values(ascending=False).reset_index().iloc[0]
        evidence.append({"label": "Top category", "value": f"{row['Category']} ({money(row['Sales'])})", "source": "Sales grouped by Category"})
    return evidence


def active_filtered(body=None):
    raw_df, _ = dataset_from_request()
    if raw_df is None:
        raise ValueError("Import a dataset first.")
    df = prepare_dataset(raw_df)
    filtered, *_ = filter_dataset(df, body or {})
    return filtered


def forecast_diagnostics(df):
    monthly, _ = predict_sales(df.copy())
    values = monthly["Sales"].astype(float).reset_index(drop=True)
    if len(values) < 7:
        return {"status": "Needs at least 7 months", "mae": None, "mape": None, "accuracy": None, "actual": [], "predicted": []}
    actual, predicted = [], []
    start = max(3, len(values) - 6)
    for index in range(start, len(values)):
        history = values.iloc[:index]
        window = min(3, len(history))
        predicted.append(float(history.iloc[-window:].mean()))
        actual.append(float(values.iloc[index]))
    errors = np.abs(np.array(actual) - np.array(predicted))
    mape = float(np.mean(errors / np.maximum(np.abs(actual), 1)) * 100)
    return {
        "status": "Backtested",
        "mae": round(float(errors.mean()), 2),
        "mape": round(mape, 1),
        "accuracy": round(max(0, 100 - mape), 1),
        "actual": [round(v, 2) for v in actual],
        "predicted": [round(v, 2) for v in predicted],
        "labels": monthly["Order Date"].astype(str).tolist()[-len(actual):],
        "method": "Rolling three-month holdout benchmark",
    }


@app.route("/api/platform/bootstrap")
def platform_bootstrap():
    kinds = ["dashboard", "alert", "action", "schedule", "history", "connection"]
    return jsonify({
        "user": get_setting("current_user"),
        "semanticMetrics": get_setting("semantic_metrics", []),
        **{f"{kind}s": list_records(kind) for kind in kinds},
    })


@app.route("/api/platform/user", methods=["PUT"])
def platform_user():
    body = request.get_json(silent=True) or {}
    role = body.get("role", "Executive")
    if role not in {"Admin", "Analyst", "Executive"}:
        return jsonify({"error": "Role must be Admin, Analyst, or Executive."}), 400
    return jsonify(set_setting("current_user", {"name": body.get("name", "Local User"), "role": role, "workspace": body.get("workspace", "Executive Workspace")}))


@app.route("/api/platform/records/<kind>", methods=["GET", "POST"])
def platform_records(kind):
    allowed = {"dashboard", "alert", "action", "schedule", "history", "connection"}
    if kind not in allowed:
        return jsonify({"error": "Unknown record type."}), 404
    if request.method == "GET":
        return jsonify(list_records(kind))
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Name is required."}), 400
    return jsonify(add_record(kind, name, body)), 201


@app.route("/api/platform/records/<kind>/<int:record_id>", methods=["PUT", "DELETE"])
def platform_record(kind, record_id):
    record = get_record(record_id)
    if not record or record["kind"] != kind:
        return jsonify({"error": "Record not found."}), 404
    if request.method == "DELETE":
        delete_record(record_id)
        return jsonify({"deleted": True})
    return jsonify(update_record(record_id, request.get_json(silent=True) or {}))


@app.route("/api/platform/dashboards/<int:record_id>/load", methods=["POST"])
def load_dashboard(record_id):
    record = get_record(record_id)
    if not record or record["kind"] != "dashboard":
        return jsonify({"error": "Dashboard not found."}), 404
    raw_df, source = dataset_from_request()
    if raw_df is None:
        return jsonify({"error": "Load the dashboard's dataset first."}), 400
    payload, status = analysis_payload(raw_df, source, record["payload"])
    return jsonify(payload), status


@app.route("/api/platform/scenario", methods=["POST"])
def platform_scenario():
    body = request.get_json(silent=True) or {}
    try:
        df = active_filtered(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    baseline = plain_metrics(df)
    volume = float(body.get("volumeChange", 0)) / 100
    price = float(body.get("priceChange", 0)) / 100
    cost = float(body.get("costChange", 0)) / 100
    discount = float(body.get("discountChange", 0)) / 100
    projected_sales = baseline["sales"] * (1 + volume) * (1 + price) * (1 - discount)
    baseline_cost = baseline["sales"] - baseline["profit"]
    projected_profit = projected_sales - baseline_cost * (1 + volume) * (1 + cost)
    return jsonify({"baseline": baseline, "projected": {"sales": projected_sales, "profit": projected_profit, "margin": projected_profit / projected_sales if projected_sales else 0}, "inputs": body})


@app.route("/api/platform/forecast-diagnostics")
def platform_forecast_diagnostics():
    try:
        return jsonify(forecast_diagnostics(active_filtered()))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/platform/chart", methods=["POST"])
def platform_chart():
    body = request.get_json(silent=True) or {}
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "Describe the chart you want."}), 400
    try:
        df = active_filtered(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    lowered = prompt.lower()
    dimension = next((col for key, col in [("region", "Region"), ("category", "Category"), ("segment", "Segment"), ("product", "Product Name"), ("month", "Order Date")] if key in lowered and col in df.columns), "Category")
    measure = "Profit" if "profit" in lowered or "margin" in lowered else "Sales"
    chart_type = "line" if "line" in lowered or dimension == "Order Date" else "pie" if "pie" in lowered else "bar"
    if dimension == "Order Date":
        grouped = df.groupby(df[dimension].dt.to_period("M"))[measure].sum().sort_index()
    else:
        grouped = df.groupby(dimension)[measure].sum().sort_values(ascending=False).head(20)
    add_record("history", prompt[:80], {"type": "Generated chart", "prompt": prompt})
    return jsonify({"title": f"{measure} by {dimension}", "type": chart_type, "labels": [str(v) for v in grouped.index], "values": grouped.round(2).tolist(), "explanation": f"Interpreted '{prompt}' as SUM({measure}) grouped by {dimension}."})


@app.route("/api/platform/alerts/evaluate", methods=["POST"])
def evaluate_alerts():
    try:
        metrics = plain_metrics(active_filtered())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    evaluated = []
    for record in list_records("alert"):
        rule = record["payload"]
        value = float(metrics.get(rule.get("metric"), 0))
        threshold = float(rule.get("threshold", 0))
        triggered = value < threshold if rule.get("operator") == "below" else value > threshold
        evaluated.append({**record, "currentValue": value, "triggered": triggered})
    return jsonify(evaluated)


@app.route("/api/platform/metrics", methods=["GET", "PUT"])
def platform_metrics():
    if request.method == "GET":
        return jsonify(get_setting("semantic_metrics", []))
    metrics = request.get_json(silent=True) or []
    if not isinstance(metrics, list):
        return jsonify({"error": "Metrics must be a list."}), 400
    return jsonify(set_setting("semantic_metrics", metrics))


@app.route("/api/platform/clean", methods=["POST"])
def platform_clean():
    body = request.get_json(silent=True) or {}
    raw_df, source = dataset_from_request()
    if raw_df is None:
        return jsonify({"error": "Import a dataset first."}), 400
    cleaned = raw_df.copy()
    before = len(cleaned)
    if body.get("removeDuplicates", True):
        cleaned = cleaned.drop_duplicates()
    if body.get("fillNumeric", False):
        for column in cleaned.select_dtypes(include="number").columns:
            cleaned[column] = cleaned[column].fillna(cleaned[column].median())
    ACTIVE_DATASET.update({"df": cleaned, "source": f"Cleaned {source}"})
    persist_active_dataset(cleaned, ACTIVE_DATASET["source"])
    payload, status = analysis_payload(cleaned, ACTIVE_DATASET["source"])
    if status == 200:
        payload["cleaningSummary"] = {"rowsBefore": before, "rowsAfter": len(cleaned), "duplicatesRemoved": before - len(cleaned)}
        add_record("history", f"Cleaned {source}", {"type": "Data preparation", **payload["cleaningSummary"]})
    return jsonify(payload), status


@app.route("/api/platform/connect", methods=["POST"])
def platform_connect():
    body = request.get_json(silent=True) or {}
    kind = body.get("type", "sqlite")
    if kind != "sqlite":
        return jsonify({"error": "This connector imports SQLite source data only. AURA-BI persistence is MongoDB-backed."}), 400
    database = Path(str(body.get("database", ""))).resolve()
    try:
        database.relative_to(ROOT_DIR)
    except ValueError:
        return jsonify({"error": "For safety, the SQLite database must be inside this project folder."}), 400
    table = str(body.get("table", ""))
    if not table or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        return jsonify({"error": "Enter a valid table name."}), 400
    try:
        with sqlite3.connect(database) as db:
            raw_df = pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT 100000', db)
        payload, status = analysis_payload(raw_df, f"{database.name}:{table}")
        if status == 200:
            ACTIVE_DATASET.update({"df": raw_df, "source": f"{database.name}:{table}"})
            persist_active_dataset(raw_df, ACTIVE_DATASET["source"])
            add_record("connection", f"{database.name}:{table}", {"type": "sqlite", "database": str(database), "table": table})
        return jsonify(payload), status
    except Exception as exc:
        return jsonify({"error": f"Connection failed: {exc}"}), 400


if __name__ == "__main__":
    port = int(__import__("os").environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
