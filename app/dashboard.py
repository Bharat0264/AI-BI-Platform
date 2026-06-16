import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
from flask import Flask
from flask import Response
from flask import render_template_string
from flask import request
from flask import send_file
from flask import url_for

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from autonomous_insights import generate_autonomous_insights
from llm_engine import ask_ai
from prediction import predict_sales
from report_generator import generate_pdf_report


server = Flask(__name__)

DEMO_DATA_PATH = ROOT_DIR / "data" / "Sample - Superstore.csv"
REQUIRED_COLUMNS = [
    "Order ID",
    "Order Date",
    "Region",
    "Category",
    "Sales",
    "Profit",
    "Discount",
]
PLOT_COLORS = ["#14b8a6", "#f97316", "#7c3aed", "#0ea5e9", "#ef4444", "#84cc16"]


def money(value):
    return f"${value:,.0f}"


def percent(value):
    if pd.isna(value):
        return "0%"
    return f"{value:.0%}"


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


def load_dataset():
    uploaded = request.files.get("dataset")
    if uploaded and uploaded.filename:
        raw_df = read_csv(uploaded)
        return raw_df, uploaded.filename

    raw_df = read_csv(DEMO_DATA_PATH)
    return raw_df, "Sample - Superstore.csv"


def filter_dataset(df):
    selected_regions = request.values.getlist("region")
    selected_categories = request.values.getlist("category")

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


def get_metrics(df):
    total_sales = df["Sales"].sum()
    total_profit = df["Profit"].sum()
    total_orders = df["Order ID"].nunique()
    avg_discount = df["Discount"].mean()
    profit_margin = total_profit / total_sales if total_sales else 0
    return [
        ("Total Sales", money(total_sales), "Revenue across selected records"),
        ("Total Profit", money(total_profit), "Net contribution after costs"),
        ("Orders", f"{total_orders:,}", "Unique customer orders"),
        ("Avg Discount", percent(avg_discount), "Average discount rate"),
        ("Profit Margin", percent(profit_margin), "Profit as a share of sales"),
    ]


def run_data_quality_scan(raw_df, prepared_df):
    invalid_dates = pd.to_datetime(raw_df.get("Order Date"), errors="coerce").isna().sum()
    missing_cells = int(raw_df.isna().sum().sum())
    duplicate_rows = int(raw_df.duplicated().sum())
    missing_required = validate_dataset(raw_df)
    score = 100
    score -= min(30, len(missing_required) * 12)
    score -= min(20, missing_cells // max(len(raw_df), 1))
    score -= min(20, int(invalid_dates))
    score -= min(15, duplicate_rows)
    return {
        "score": max(score, 0),
        "rows": len(raw_df),
        "clean_rows": len(prepared_df),
        "columns": len(raw_df.columns),
        "missing_cells": missing_cells,
        "duplicate_rows": duplicate_rows,
        "invalid_dates": int(invalid_dates),
        "missing_required": ", ".join(missing_required) if missing_required else "None",
    }


def build_advanced_insights(df):
    total_sales = df["Sales"].sum()
    total_profit = df["Profit"].sum()
    margin = total_profit / total_sales if total_sales else 0
    avg_discount = df["Discount"].mean()
    category_sales = df.groupby("Category")["Sales"].sum().sort_values(ascending=False)
    region_profit = df.groupby("Region")["Profit"].sum().sort_values()
    loss_df = df[df["Profit"] < 0]

    top_category = category_sales.index[0] if not category_sales.empty else "N/A"
    weakest_region = region_profit.index[0] if not region_profit.empty else "N/A"
    strongest_region = region_profit.index[-1] if not region_profit.empty else "N/A"

    return [
        ("Revenue opportunity", f"{top_category} is the strongest category. Build campaigns and bundles around it."),
        ("Profit leak", f"{len(loss_df):,} transactions are loss-making. Review discounting, shipping cost, and product mix."),
        ("Regional risk", f"{weakest_region} has the weakest profit contribution while {strongest_region} leads performance."),
        ("Pricing pressure", f"Average discount is {percent(avg_discount)}. Keep discounts below margin-protecting thresholds."),
        ("Executive action", f"Current margin is {percent(margin)}. Prioritize high-margin categories before chasing pure revenue growth."),
    ]


def detect_anomalies(df):
    anomalies = []
    losses = df[df["Profit"] < 0]
    if not losses.empty:
        worst = losses.sort_values("Profit").iloc[0]
        anomalies.append(("Largest loss", f"{worst.get('Category', 'Unknown')} in {worst.get('Region', 'Unknown')} lost {money(abs(worst['Profit']))}."))

    high_discount = df[df["Discount"] >= 0.5]
    if not high_discount.empty:
        anomalies.append(("High discounts", f"{len(high_discount):,} rows have discounts of 50% or more."))

    monthly = df.groupby(df["Order Date"].dt.to_period("M"))["Sales"].sum()
    if len(monthly) >= 3:
        latest = monthly.iloc[-1]
        average = monthly.iloc[:-1].mean()
        if average and latest < average * 0.75:
            anomalies.append(("Recent slowdown", f"Latest monthly sales are {money(latest)}, below the prior average of {money(average)}."))

    if not anomalies:
        anomalies.append(("No major anomaly", "No extreme losses, discount spikes, or recent sales breaks were detected."))
    return anomalies


def figure_html(fig):
    fig.update_layout(
        template="plotly_white",
        height=390,
        margin=dict(l=14, r=14, t=48, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font=dict(color="#101828", family="Inter, Segoe UI, sans-serif"),
    )
    fig.update_xaxes(showgrid=False, linecolor="rgba(16, 24, 40, 0.12)")
    fig.update_yaxes(gridcolor="rgba(16, 24, 40, 0.08)", zeroline=False)
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})


def chart_bundle(df):
    category_sales = df.groupby("Category")["Sales"].sum().reset_index()
    region_profit = df.groupby("Region")["Profit"].sum().reset_index()
    monthly_sales = (
        df.groupby(df["Order Date"].dt.to_period("M"))["Sales"]
        .sum()
        .reset_index()
    )
    monthly_sales["Order Date"] = monthly_sales["Order Date"].astype(str)

    return {
        "category": figure_html(px.bar(category_sales, x="Category", y="Sales", color="Category", color_discrete_sequence=PLOT_COLORS, title="Sales by Category")),
        "region": figure_html(px.bar(region_profit, x="Region", y="Profit", color="Region", color_discrete_sequence=PLOT_COLORS, title="Profit by Region")),
        "monthly": figure_html(px.line(monthly_sales, x="Order Date", y="Sales", markers=True, title="Monthly Sales Trend")),
    }


def forecast_chart(monthly_sales, forecast):
    fig = px.line(monthly_sales, x="Order Date", y="Sales", markers=True, title="Sales Forecast")
    if not forecast.empty:
        fig.add_scatter(x=forecast["Forecast Month"], y=forecast["Predicted Sales"], mode="lines+markers", name="Forecast")
        fig.add_scatter(x=forecast["Forecast Month"], y=forecast["Upper Bound"], mode="lines", name="Upper bound", line=dict(width=0), showlegend=False)
        fig.add_scatter(x=forecast["Forecast Month"], y=forecast["Lower Bound"], mode="lines", name="Lower bound", fill="tonexty", line=dict(width=0), fillcolor="rgba(20,184,166,0.16)", showlegend=False)
    return figure_html(fig)


def dataframe_csv(df):
    return df.to_csv(index=False).encode("utf-8")


def encoded_query(selected_regions, selected_categories):
    parts = []
    for region in selected_regions:
        parts.append(("region", region))
    for category in selected_categories:
        parts.append(("category", category))
    return parts


def build_context():
    raw_df, source_name = load_dataset()
    missing_columns = validate_dataset(raw_df)
    if missing_columns:
        return {"error": f"This CSV is missing required columns: {', '.join(missing_columns)}."}

    df = prepare_dataset(raw_df)
    if df.empty:
        return {"error": "No valid dated rows were found after processing the dataset."}

    filtered_df, regions, categories, selected_regions, selected_categories = filter_dataset(df)
    if filtered_df.empty:
        return {"error": "No rows match the selected filters."}

    monthly_sales, forecast = predict_sales(filtered_df.copy())
    ai_prompt = request.values.get("prompt", "").strip()
    ai_answer = None
    if ai_prompt:
        ai_answer = ask_ai(ai_prompt, filtered_df)

    return {
        "error": None,
        "source_name": source_name,
        "raw_df": raw_df,
        "df": df,
        "filtered_df": filtered_df,
        "regions": regions,
        "categories": categories,
        "selected_regions": selected_regions,
        "selected_categories": selected_categories,
        "metrics": get_metrics(filtered_df),
        "quality": run_data_quality_scan(raw_df, df),
        "insights": build_advanced_insights(filtered_df),
        "classic_insights": generate_autonomous_insights(filtered_df),
        "anomalies": detect_anomalies(filtered_df),
        "charts": chart_bundle(filtered_df),
        "monthly_sales": monthly_sales,
        "forecast": forecast,
        "forecast_chart": forecast_chart(monthly_sales, forecast),
        "ai_prompt": ai_prompt,
        "ai_answer": ai_answer,
        "active_page": request.values.get("page", "dashboard"),
        "query_pairs": encoded_query(selected_regions, selected_categories),
    }


PAGE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI BI Platform</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root { --ink:#101828; --muted:#667085; --line:#d0d5dd; --accent:#14b8a6; --accent-dark:#0f766e; --warm:#f97316; --canvas:#f4f7fb; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Inter, Segoe UI, Arial, sans-serif; color:var(--ink); background:linear-gradient(180deg,#f8fbff 0%,#eef4f8 100%); }
    a { color: inherit; text-decoration: none; }
    .layout { display:grid; grid-template-columns: 292px 1fr; min-height:100vh; }
    aside { background:#111827; color:#f8fafc; padding:24px 18px; position:sticky; top:0; height:100vh; overflow:auto; }
    .brand { font-size:1.05rem; font-weight:900; margin-bottom:4px; }
    .caption { color:#cbd5e1; font-size:.86rem; line-height:1.45; }
    .nav { display:grid; gap:8px; margin:24px 0; }
    .nav a { padding:11px 12px; border-radius:8px; color:#e5e7eb; font-weight:750; }
    .nav a.active, .nav a:hover { background:rgba(20,184,166,.16); color:white; }
    label { display:block; margin:14px 0 8px; font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; font-weight:850; color:#cbd5e1; }
    select, textarea, input[type=file] { width:100%; border:1px solid rgba(255,255,255,.16); border-radius:8px; padding:10px; background:rgba(255,255,255,.08); color:white; }
    option { color:#111827; }
    button, .button { border:0; border-radius:8px; background:linear-gradient(135deg,var(--accent),var(--accent-dark)); color:white; font-weight:850; padding:11px 14px; cursor:pointer; display:inline-flex; justify-content:center; align-items:center; min-height:42px; }
    .secondary { background:#f8fafc; color:#111827; border:1px solid var(--line); }
    .main { padding:28px; max-width:1440px; width:100%; margin:0 auto; }
    .hero { color:white; background:linear-gradient(135deg,#101828,#0f766e); border-radius:8px; padding:32px; box-shadow:0 24px 70px rgba(15,23,42,.20); margin-bottom:22px; }
    .hero h1 { margin:0; font-size:clamp(2.1rem,5vw,4.7rem); line-height:1; letter-spacing:0; max-width:920px; }
    .hero p { max-width:780px; color:rgba(255,255,255,.76); line-height:1.7; }
    .eyebrow { color:#99f6e4; text-transform:uppercase; letter-spacing:.1em; font-size:.78rem; font-weight:900; margin-bottom:12px; }
    .pill-row { display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }
    .pill { border:1px solid rgba(255,255,255,.18); background:rgba(255,255,255,.10); color:#ecfeff; border-radius:999px; padding:8px 12px; font-size:.82rem; font-weight:800; }
    .grid { display:grid; gap:16px; }
    .metrics { grid-template-columns:repeat(5,minmax(0,1fr)); }
    .two { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .three { grid-template-columns:repeat(3,minmax(0,1fr)); }
    .card, .panel { background:rgba(255,255,255,.86); border:1px solid rgba(255,255,255,.9); box-shadow:0 18px 50px rgba(16,24,40,.09); border-radius:8px; padding:20px; }
    .metric-label { color:var(--muted); font-size:.76rem; text-transform:uppercase; letter-spacing:.08em; font-weight:900; }
    .metric-value { margin-top:10px; font-size:1.75rem; font-weight:950; }
    .metric-note { margin-top:8px; color:var(--muted); font-size:.88rem; }
    h2 { margin:30px 0 12px; font-size:1.35rem; }
    h3 { margin:0 0 8px; font-size:1rem; }
    .muted { color:var(--muted); }
    .table { width:100%; border-collapse:collapse; overflow:hidden; border-radius:8px; }
    .table th, .table td { padding:11px 12px; border-bottom:1px solid #e4e7ec; text-align:left; font-size:.92rem; }
    .table th { background:#0f766e; color:white; }
    .actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:14px; }
    .assistant textarea { min-height:130px; background:white; color:var(--ink); border-color:var(--line); }
    .answer { white-space:pre-wrap; line-height:1.6; }
    .alert { padding:16px; border-radius:8px; background:#fff7ed; border:1px solid #fed7aa; color:#9a3412; }
    @media (max-width: 980px) { .layout { grid-template-columns:1fr; } aside { position:relative; height:auto; } .metrics, .two, .three { grid-template-columns:1fr; } .main { padding:18px; } }
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <div class="brand">AI BI Platform</div>
      <div class="caption">Executive analytics workspace</div>
      <nav class="nav">
        {% for key, label in [("dashboard","Dashboard"),("quality","Data Quality"),("forecast","Forecasting"),("insights","Insights"),("assistant","AI Assistant"),("exports","Exports")] %}
          <a class="{{ 'active' if active_page == key else '' }}" href="{{ url_for('index', page=key) }}">{{ label }}</a>
        {% endfor %}
      </nav>
      <form method="get">
        <input type="hidden" name="page" value="{{ active_page }}">
        <label>Region</label>
        <select name="region" multiple size="4">
          {% for region in regions %}
            <option value="{{ region }}" {{ 'selected' if region in selected_regions else '' }}>{{ region }}</option>
          {% endfor %}
        </select>
        <label>Category</label>
        <select name="category" multiple size="4">
          {% for category in categories %}
            <option value="{{ category }}" {{ 'selected' if category in selected_categories else '' }}>{{ category }}</option>
          {% endfor %}
        </select>
        <div class="actions"><button type="submit">Apply Filters</button><a class="button secondary" href="{{ url_for('index') }}">Reset</a></div>
      </form>
      <p class="caption" style="margin-top:24px;">Source: {{ source_name }}<br>{{ filtered_df|length }} filtered rows</p>
    </aside>
    <main class="main">
      {% if error %}
        <div class="alert">{{ error }}</div>
      {% else %}
      <section class="hero">
        <div class="eyebrow">Autonomous analytics command center</div>
        <h1>AI Business Intelligence Platform</h1>
        <p>Upload a business CSV or use the included demo dataset to explore KPIs, data quality, anomaly detection, AI recommendations, forecasts, and board-ready reports.</p>
        <form method="post" enctype="multipart/form-data" class="actions">
          <input type="hidden" name="page" value="{{ active_page }}">
          <input type="file" name="dataset" accept=".csv">
          <button type="submit">Analyze CSV</button>
        </form>
      </section>

      {% if active_page == "dashboard" %}
        <section class="grid metrics">
          {% for label, value, note in metrics %}
            <article class="card"><div class="metric-label">{{ label }}</div><div class="metric-value">{{ value }}</div><div class="metric-note">{{ note }}</div></article>
          {% endfor %}
        </section>
        <h2>Performance Dashboard</h2>
        <section class="grid two"><div class="panel">{{ charts.category|safe }}</div><div class="panel">{{ charts.region|safe }}</div></section>
        <h2>Trend Analysis</h2>
        <section class="panel">{{ charts.monthly|safe }}</section>
      {% elif active_page == "quality" %}
        <h2>Data Quality</h2>
        <section class="grid three">
          {% for label, value in quality.items() %}
            <article class="card"><div class="metric-label">{{ label.replace('_', ' ') }}</div><div class="metric-value">{{ value }}</div></article>
          {% endfor %}
        </section>
        <h2>Cleaned Data Preview</h2>
        <section class="panel">{{ preview|safe }}</section>
      {% elif active_page == "forecast" %}
        <h2>Forecasting</h2>
        <section class="panel">{{ forecast_chart|safe }}</section>
        <h2>Six-Month Forecast</h2>
        <section class="panel">{{ forecast_table|safe }}</section>
      {% elif active_page == "insights" %}
        <h2>Autonomous Recommendations</h2>
        <section class="grid two">{% for title, body in insights %}<article class="card"><h3>{{ title }}</h3><p class="muted">{{ body }}</p></article>{% endfor %}</section>
        <h2>Anomalies</h2>
        <section class="grid two">{% for title, body in anomalies %}<article class="card"><h3>{{ title }}</h3><p class="muted">{{ body }}</p></article>{% endfor %}</section>
        <h2>Classic Insight Engine</h2>
        <section class="grid two">{% for item in classic_insights %}<article class="card"><p>{{ item }}</p></article>{% endfor %}</section>
      {% elif active_page == "assistant" %}
        <h2>AI Assistant</h2>
        <section class="panel assistant">
          <form method="post">
            <input type="hidden" name="page" value="assistant">
            {% for key, value in query_pairs %}<input type="hidden" name="{{ key }}" value="{{ value }}">{% endfor %}
            <textarea name="prompt" placeholder="Ask a business question...">{{ ai_prompt }}</textarea>
            <div class="actions"><button type="submit">Analyze with AI</button></div>
          </form>
          {% if ai_answer %}<h2>Answer</h2><div class="answer">{{ ai_answer }}</div>{% endif %}
        </section>
      {% elif active_page == "exports" %}
        <h2>Export Center</h2>
        <section class="grid two">
          <a class="button" href="{{ url_for('download_filtered') }}">Download Filtered CSV</a>
          <a class="button" href="{{ url_for('download_forecast') }}">Download Forecast CSV</a>
          <a class="button" href="{{ url_for('download_report') }}">Generate PDF Report</a>
        </section>
      {% endif %}
      {% endif %}
    </main>
  </div>
</body>
</html>
"""


@server.route("/", methods=["GET", "POST"])
def index():
    context = build_context()
    if context["error"]:
        return render_template_string(PAGE_TEMPLATE, **context)

    context["preview"] = context["df"].head(50).to_html(classes="table", index=False)
    forecast = context["forecast"].copy()
    if not forecast.empty:
        for column in ["Predicted Sales", "Lower Bound", "Upper Bound"]:
            forecast[column] = forecast[column].map(money)
    context["forecast_table"] = forecast.to_html(classes="table", index=False)
    return render_template_string(PAGE_TEMPLATE, **context)


@server.route("/download/filtered")
def download_filtered():
    raw_df = read_csv(DEMO_DATA_PATH)
    df = prepare_dataset(raw_df)
    filtered_df, *_ = filter_dataset(df)
    return Response(
        dataframe_csv(filtered_df),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=filtered_business_data.csv"},
    )


@server.route("/download/forecast")
def download_forecast():
    raw_df = read_csv(DEMO_DATA_PATH)
    df = prepare_dataset(raw_df)
    filtered_df, *_ = filter_dataset(df)
    _, forecast = predict_sales(filtered_df.copy())
    return Response(
        dataframe_csv(forecast),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales_forecast.csv"},
    )


@server.route("/download/report")
def download_report():
    raw_df = read_csv(DEMO_DATA_PATH)
    df = prepare_dataset(raw_df)
    filtered_df, *_ = filter_dataset(df)
    _, forecast = predict_sales(filtered_df.copy())
    insights = [{"title": title, "body": body} for title, body in build_advanced_insights(filtered_df)]
    anomalies = [{"title": title, "body": body} for title, body in detect_anomalies(filtered_df)]
    metrics = {label: value for label, value, _ in get_metrics(filtered_df)}
    report_text = "Automated executive snapshot generated from the current business dataset."
    pdf_path = generate_pdf_report(report_text, metrics=metrics, insights=insights, anomalies=anomalies, forecast=forecast)
    return send_file(pdf_path, as_attachment=True, download_name="AI_Business_Report.pdf")


app = server


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=5000, debug=True)
