import sys
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

from llm_engine import ask_ai
from prediction import predict_sales
from report_generator import generate_pdf_report


app = Flask(__name__, static_folder="frontend", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 24 * 1024 * 1024

DATA_PATH = ROOT_DIR / "data" / "Sample - Superstore.csv"
ACTIVE_DATASET = {"df": None, "source": None}
REQUIRED_COLUMNS = [
    "Order ID",
    "Order Date",
    "Region",
    "Category",
    "Sales",
    "Profit",
    "Discount",
]


def read_csv(source):
    return pd.read_csv(source, encoding="latin1")


def validate_dataset(df):
    return [column for column in REQUIRED_COLUMNS if column not in df.columns]


def prepare_dataset(df):
    prepared = df.copy()
    prepared["Order Date"] = pd.to_datetime(prepared["Order Date"], errors="coerce")
    prepared["Sales"] = pd.to_numeric(prepared["Sales"], errors="coerce").fillna(0)
    prepared["Profit"] = pd.to_numeric(prepared["Profit"], errors="coerce").fillna(0)
    prepared["Discount"] = pd.to_numeric(prepared["Discount"], errors="coerce").fillna(0)
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
        return read_csv(uploaded), uploaded.filename
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


def analysis_payload(raw_df, source_name, payload=None):
    missing = validate_dataset(raw_df)
    if missing:
        return {"error": f"Missing required columns: {', '.join(missing)}"}, 400

    df = prepare_dataset(raw_df)
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

    return {
        "source": source_name,
        "rows": int(len(filtered)),
        "regions": regions,
        "categories": categories,
        "selectedRegions": selected_regions,
        "selectedCategories": selected_categories,
        "metrics": kpis(filtered),
        "quality": quality_scan(raw_df, df),
        "datasetProfile": dataset_profile(raw_df, df, filtered, source_name),
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
        "preview": filtered.head(25).fillna("").to_dict(orient="records"),
    }, 200


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


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
    return jsonify(empty_payload())


@app.route("/api/upload", methods=["POST"])
def api_upload():
    uploaded = request.files.get("dataset")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Choose a CSV file to import."}), 400
    if not uploaded.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files are supported."}), 400

    raw_df, source_name = read_csv(uploaded), uploaded.filename
    payload, status = analysis_payload(raw_df, source_name)
    if status == 200:
        ACTIVE_DATASET["df"] = raw_df.copy()
        ACTIVE_DATASET["source"] = source_name
    return jsonify(payload), status


@app.route("/api/demo", methods=["POST"])
def api_demo():
    if not DATA_PATH.exists():
        return jsonify({"error": "Demo dataset is not available on this deployment."}), 404
    raw_df = read_csv(DATA_PATH)
    payload, status = analysis_payload(raw_df, DATA_PATH.name)
    if status == 200:
        ACTIVE_DATASET["df"] = raw_df.copy()
        ACTIVE_DATASET["source"] = DATA_PATH.name
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
    df = prepare_dataset(raw_df)
    filtered, *_ = filter_dataset(df, body)
    answer = ask_ai(question, filtered)
    return jsonify({"answer": answer})


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
    pdf_path = generate_pdf_report(
        "\n\n".join([f"{item['label']}: {item['detail']}" for item in summary]),
        metrics=metrics,
        insights=recommendations(filtered),
        anomalies=anomalies(filtered),
        forecast=forecast,
    )
    return send_file(pdf_path, as_attachment=True, download_name="AI_Business_Report.pdf")


if __name__ == "__main__":
    port = int(__import__("os").environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
