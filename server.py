import sys
from pathlib import Path

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


def percent(value):
    if pd.isna(value):
        return "0%"
    return f"{value:.0%}"


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
    return [
        {"label": "Total Sales", "value": money(total_sales), "note": "Revenue across selected records"},
        {"label": "Total Profit", "value": money(total_profit), "note": "Net contribution after costs"},
        {"label": "Orders", "value": f"{total_orders:,}", "note": "Unique customer orders"},
        {"label": "Avg Discount", "value": percent(avg_discount), "note": "Average discount rate"},
        {"label": "Profit Margin", "value": percent(profit_margin), "note": "Profit as a share of sales"},
    ]


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


def anomalies(df):
    items = []
    losses = df[df["Profit"] < 0]
    if not losses.empty:
        worst = losses.sort_values("Profit").iloc[0]
        items.append({"title": "Largest loss", "body": f"{worst.get('Category', 'Unknown')} in {worst.get('Region', 'Unknown')} lost {money(abs(worst['Profit']))}."})
    high_discount = df[df["Discount"] >= 0.5]
    if not high_discount.empty:
        items.append({"title": "High discounts", "body": f"{len(high_discount):,} rows have discounts of 50% or more."})
    if not items:
        items.append({"title": "No major anomaly", "body": "No extreme losses or discount spikes were detected."})
    return items


def group_records(df, group_col, value_col):
    data = df.groupby(group_col)[value_col].sum().reset_index()
    return data[group_col].astype(str).tolist(), data[value_col].round(2).tolist()


def monthly_records(df):
    data = (
        df.groupby(df["Order Date"].dt.to_period("M"))["Sales"]
        .sum()
        .reset_index()
        .sort_values("Order Date")
    )
    data["Order Date"] = data["Order Date"].astype(str)
    return data["Order Date"].tolist(), data["Sales"].round(2).tolist()


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
        "charts": {
            "categorySales": {"labels": category_labels, "values": category_values},
            "regionProfit": {"labels": region_labels, "values": region_values},
            "monthlySales": {"labels": month_labels, "values": month_values},
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


@app.route("/api/upload", methods=["POST"])
def api_upload():
    uploaded = request.files.get("dataset")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Choose a CSV file to import."}), 400

    raw_df, source_name = read_csv(uploaded), uploaded.filename
    payload, status = analysis_payload(raw_df, source_name)
    if status == 200:
        ACTIVE_DATASET["df"] = raw_df.copy()
        ACTIVE_DATASET["source"] = source_name
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
    pdf_path = generate_pdf_report(
        "Automated executive snapshot generated from the current business dataset.",
        metrics=metrics,
        insights=recommendations(filtered),
        anomalies=anomalies(filtered),
        forecast=forecast,
    )
    return send_file(pdf_path, as_attachment=True, download_name="AI_Business_Report.pdf")


if __name__ == "__main__":
    port = int(__import__("os").environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
