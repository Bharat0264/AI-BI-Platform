from html import escape
from io import StringIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from autonomous_insights import generate_autonomous_insights
from llm_engine import ask_ai
from prediction import predict_sales
from report_generator import generate_pdf_report
from streamlit_mic_recorder import mic_recorder


BASE_DIR = Path(__file__).resolve().parents[1]
DEMO_DATA_PATH = BASE_DIR / "data" / "Sample - Superstore.csv"

REQUIRED_COLUMNS = [
    "Order ID",
    "Order Date",
    "Region",
    "Category",
    "Sales",
    "Profit",
    "Discount",
]

ACCENT = "#17c3b2"
INK = "#101828"
MUTED = "#667085"
PLOT_COLORS = ["#17c3b2", "#f97316", "#7c3aed", "#0ea5e9", "#ef4444", "#84cc16"]


st.set_page_config(
    page_title="AI BI Platform",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_theme():
    st.markdown(
        """
        <style>
            :root {
                --ink: #101828;
                --muted: #667085;
                --line: rgba(16, 24, 40, 0.10);
                --panel: rgba(255, 255, 255, 0.88);
                --accent: #17c3b2;
                --accent-dark: #0f766e;
                --warm: #f97316;
                --canvas: #f7f9fc;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(23, 195, 178, 0.14), transparent 32rem),
                    radial-gradient(circle at top right, rgba(249, 115, 22, 0.10), transparent 30rem),
                    linear-gradient(180deg, #f8fbff 0%, #eef4f8 100%);
                color: var(--ink);
            }

            [data-testid="stHeader"] { background: transparent; }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
                border-right: 1px solid rgba(255, 255, 255, 0.08);
            }

            [data-testid="stSidebar"] * { color: #f8fafc !important; }

            [data-testid="stSidebar"] [data-baseweb="select"] > div,
            [data-testid="stSidebar"] [data-baseweb="input"] {
                background: rgba(255, 255, 255, 0.08);
                border-color: rgba(255, 255, 255, 0.14);
                border-radius: 12px;
            }

            .block-container {
                max-width: 1400px;
                padding-top: 2rem;
                padding-bottom: 3rem;
            }

            .hero {
                position: relative;
                overflow: hidden;
                border: 1px solid rgba(255, 255, 255, 0.75);
                border-radius: 28px;
                padding: 34px;
                background:
                    linear-gradient(135deg, rgba(16, 24, 40, 0.95), rgba(15, 118, 110, 0.88)),
                    linear-gradient(45deg, rgba(23, 195, 178, 0.6), rgba(249, 115, 22, 0.45));
                box-shadow: 0 24px 70px rgba(15, 23, 42, 0.22);
                margin-bottom: 22px;
            }

            .hero:after {
                content: "";
                position: absolute;
                inset: auto -60px -130px auto;
                width: 360px;
                height: 360px;
                background: conic-gradient(from 140deg, rgba(23, 195, 178, 0.48), rgba(249, 115, 22, 0.42), transparent);
                filter: blur(8px);
                opacity: 0.75;
                transform: rotate(-12deg);
            }

            .eyebrow {
                color: #99f6e4;
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.10em;
                text-transform: uppercase;
                margin-bottom: 12px;
            }

            .hero h1 {
                color: #ffffff;
                font-size: clamp(2.2rem, 5vw, 4.8rem);
                line-height: 0.96;
                letter-spacing: 0;
                margin: 0;
                max-width: 920px;
            }

            .hero p {
                color: rgba(255, 255, 255, 0.76);
                font-size: 1.05rem;
                line-height: 1.7;
                max-width: 780px;
                margin: 18px 0 0 0;
            }

            .pill-row {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 24px;
            }

            .pill {
                display: inline-flex;
                align-items: center;
                min-height: 34px;
                padding: 7px 12px;
                border-radius: 999px;
                color: #ecfeff;
                background: rgba(255, 255, 255, 0.10);
                border: 1px solid rgba(255, 255, 255, 0.18);
                font-size: 0.82rem;
                font-weight: 700;
            }

            .metric-card,
            .glass-panel,
            .insight-card,
            .upload-shell {
                background: rgba(255, 255, 255, 0.82);
                border: 1px solid rgba(255, 255, 255, 0.88);
                box-shadow: 0 18px 50px rgba(16, 24, 40, 0.10);
            }

            .metric-card {
                min-height: 154px;
                padding: 22px;
                border-radius: 20px;
            }

            .metric-label {
                color: var(--muted);
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            .metric-value {
                color: var(--ink);
                font-size: 2rem;
                font-weight: 900;
                letter-spacing: 0;
                margin-top: 10px;
            }

            .metric-note {
                color: var(--muted);
                font-size: 0.88rem;
                margin-top: 8px;
            }

            .section-title {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                margin: 28px 0 12px 0;
            }

            .section-title h2 {
                color: var(--ink);
                font-size: 1.35rem;
                margin: 0;
                letter-spacing: 0;
            }

            .section-title p {
                color: var(--muted);
                margin: 0;
                font-size: 0.95rem;
            }

            .glass-panel {
                padding: 24px;
                border-radius: 22px;
            }

            .insight-card {
                padding: 18px 20px;
                border-radius: 18px;
                min-height: 112px;
            }

            .insight-card strong {
                color: var(--ink);
                display: block;
                margin-bottom: 8px;
            }

            .insight-card span {
                color: var(--muted);
                line-height: 1.55;
            }

            .upload-shell {
                padding: 28px;
                border-radius: 24px;
            }

            div[data-testid="stFileUploader"] section {
                border: 1px dashed rgba(15, 118, 110, 0.42);
                background: rgba(23, 195, 178, 0.06);
                border-radius: 18px;
            }

            div[data-testid="stFileUploader"] label,
            div[data-testid="stFileUploader"] small,
            div[data-testid="stFileUploader"] p,
            div[data-testid="stFileUploader"] span {
                color: var(--ink) !important;
            }

            div[data-testid="stFileUploader"] button,
            div.stButton > button,
            div[data-testid="stDownloadButton"] > button {
                border-radius: 13px;
                border: 1px solid rgba(15, 118, 110, 0.22);
                background: linear-gradient(135deg, #14b8a6, #0f766e) !important;
                color: white !important;
                font-weight: 800;
                min-height: 42px;
                box-shadow: 0 10px 28px rgba(20, 184, 166, 0.23);
            }

            div[data-testid="stFileUploader"] button:hover,
            div.stButton > button:hover,
            div[data-testid="stDownloadButton"] > button:hover {
                border-color: rgba(15, 118, 110, 0.42);
                color: white !important;
                transform: translateY(-1px);
            }

            .chat-bubble-user,
            .chat-bubble-ai {
                padding: 16px 18px;
                border-radius: 18px;
                margin-bottom: 12px;
                border: 1px solid rgba(16, 24, 40, 0.08);
            }

            .chat-bubble-user {
                background: #ecfdf5;
            }

            .chat-bubble-ai {
                background: #ffffff;
            }

            .status-good { color: #0f766e; font-weight: 800; }
            .status-risk { color: #b42318; font-weight: 800; }
            .status-watch { color: #c2410c; font-weight: 800; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def money(value):
    return f"${value:,.0f}"


def percent(value):
    if pd.isna(value):
        return "0%"
    return f"{value:.0%}"


def section_title(title, caption):
    st.markdown(
        f"""
        <div class="section-title">
            <div>
                <h2>{escape(title)}</h2>
                <p>{escape(caption)}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label, value, note):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{escape(str(label))}</div>
            <div class="metric-value">{escape(str(value))}</div>
            <div class="metric-note">{escape(str(note))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def insight_card(title, body):
    st.markdown(
        f"""
        <div class="insight-card">
            <strong>{escape(str(title))}</strong>
            <span>{escape(str(body))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_figure(fig, height=420):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=16, r=16, t=54, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font=dict(color=INK, family="Inter, Segoe UI, sans-serif"),
        title=dict(font=dict(size=18, color=INK), x=0.02),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=False, linecolor="rgba(16, 24, 40, 0.12)")
    fig.update_yaxes(gridcolor="rgba(16, 24, 40, 0.08)", zeroline=False)
    return fig


def render_hero():
    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">Autonomous analytics command center</div>
            <h1>AI Business Intelligence Platform</h1>
            <p>
                Upload a business CSV or launch the demo dataset to explore executive KPIs,
                data quality, anomaly detection, AI recommendations, forecasts, and board-ready reports.
            </p>
            <div class="pill-row">
                <span class="pill">Demo-ready workflow</span>
                <span class="pill">AI analyst chat</span>
                <span class="pill">ML forecast bands</span>
                <span class="pill">Export center</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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


def get_metrics(df):
    total_sales = df["Sales"].sum()
    total_profit = df["Profit"].sum()
    total_orders = df["Order ID"].nunique()
    avg_discount = df["Discount"].mean()
    profit_margin = total_profit / total_sales if total_sales else 0
    return {
        "Total Sales": money(total_sales),
        "Total Profit": money(total_profit),
        "Orders": f"{total_orders:,}",
        "Avg Discount": percent(avg_discount),
        "Profit Margin": percent(profit_margin),
    }


def run_data_quality_scan(raw_df, prepared_df):
    invalid_dates = pd.to_datetime(raw_df.get("Order Date"), errors="coerce").isna().sum()
    missing_cells = int(raw_df.isna().sum().sum())
    duplicate_rows = int(raw_df.duplicated().sum())
    missing_required = validate_dataset(raw_df)
    numeric_issues = {}

    for column in ["Sales", "Profit", "Discount"]:
        if column in raw_df.columns:
            numeric_issues[column] = int(pd.to_numeric(raw_df[column], errors="coerce").isna().sum())

    score = 100
    score -= min(30, len(missing_required) * 12)
    score -= min(20, missing_cells // max(len(raw_df), 1))
    score -= min(20, invalid_dates)
    score -= min(15, duplicate_rows)
    score = max(score, 0)

    return {
        "score": score,
        "missing_cells": missing_cells,
        "duplicate_rows": duplicate_rows,
        "invalid_dates": int(invalid_dates),
        "missing_required": missing_required,
        "numeric_issues": numeric_issues,
        "row_count": len(raw_df),
        "clean_row_count": len(prepared_df),
        "column_count": len(raw_df.columns),
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

    insights = [
        {
            "title": "Revenue opportunity",
            "body": f"{top_category} is the strongest category. Build campaigns and bundles around this segment.",
        },
        {
            "title": "Profit leak",
            "body": f"{len(loss_df):,} transactions are loss-making. Review discounting, shipping cost, and product mix.",
        },
        {
            "title": "Regional risk",
            "body": f"{weakest_region} has the weakest profit contribution while {strongest_region} leads performance.",
        },
        {
            "title": "Pricing pressure",
            "body": f"Average discount is {percent(avg_discount)}. Keep discounts below margin-protecting thresholds.",
        },
        {
            "title": "Executive action",
            "body": f"Current margin is {percent(margin)}. Prioritize high-margin categories before chasing pure revenue growth.",
        },
    ]
    return insights


def detect_anomalies(df):
    anomalies = []

    monthly = (
        df.groupby(df["Order Date"].dt.to_period("M"))["Sales"]
        .sum()
        .reset_index()
        .sort_values("Order Date")
    )
    monthly["Sales Change"] = monthly["Sales"].pct_change()

    if len(monthly) >= 3:
        drops = monthly[monthly["Sales Change"] <= -0.25]
        for _, row in drops.tail(3).iterrows():
            anomalies.append(
                {
                    "title": f"Sales drop in {row['Order Date']}",
                    "body": f"Monthly sales fell by {abs(row['Sales Change']):.0%}. Check campaigns, inventory, and market demand.",
                }
            )

    high_discount_losses = df[(df["Discount"] >= 0.30) & (df["Profit"] < 0)]
    if not high_discount_losses.empty:
        anomalies.append(
            {
                "title": "High-discount loss cluster",
                "body": f"{len(high_discount_losses):,} rows combine discounts above 30% with negative profit.",
            }
        )

    region_profit = df.groupby("Region")["Profit"].sum()
    negative_regions = region_profit[region_profit < 0]
    for region, profit in negative_regions.items():
        anomalies.append(
            {
                "title": f"Negative regional profit: {region}",
                "body": f"This region is at {money(profit)} profit and needs margin recovery actions.",
            }
        )

    category_margin = df.groupby("Category").apply(
        lambda group: group["Profit"].sum() / group["Sales"].sum()
        if group["Sales"].sum()
        else 0,
        include_groups=False,
    )
    weak_categories = category_margin[category_margin < 0]
    for category, margin in weak_categories.items():
        anomalies.append(
            {
                "title": f"Category margin alert: {category}",
                "body": f"Category margin is {percent(margin)}. Review product economics and discount rules.",
            }
        )

    if not anomalies:
        anomalies.append(
            {
                "title": "No critical anomalies detected",
                "body": "The active filters do not show severe drops, negative regions, or high-discount loss clusters.",
            }
        )

    return anomalies[:8]


def build_category_sales_fig(df):
    category_sales = (
        df.groupby("Category", as_index=False)["Sales"].sum().sort_values("Sales", ascending=False)
    )
    fig = px.bar(
        category_sales,
        x="Category",
        y="Sales",
        color="Category",
        color_discrete_sequence=PLOT_COLORS,
        title="Revenue by Category",
    )
    fig.update_traces(marker_line_width=0, hovertemplate="%{x}<br>Sales: $%{y:,.0f}<extra></extra>")
    return style_figure(fig)


def build_region_profit_fig(df):
    region_profit = (
        df.groupby("Region", as_index=False)["Profit"].sum().sort_values("Profit", ascending=False)
    )
    fig = px.bar(
        region_profit,
        x="Region",
        y="Profit",
        color="Profit",
        color_continuous_scale=["#ef4444", "#f97316", "#17c3b2"],
        title="Profit by Region",
    )
    fig.update_traces(marker_line_width=0, hovertemplate="%{x}<br>Profit: $%{y:,.0f}<extra></extra>")
    return style_figure(fig)


def build_monthly_sales_fig(df):
    monthly_sales = (
        df.groupby(df["Order Date"].dt.to_period("M"))["Sales"].sum().reset_index()
    )
    monthly_sales["Order Date"] = monthly_sales["Order Date"].astype(str)
    fig = px.line(
        monthly_sales,
        x="Order Date",
        y="Sales",
        markers=True,
        title="Monthly Sales Trend",
    )
    fig.update_traces(
        line=dict(color=ACCENT, width=4),
        marker=dict(size=8, color="#0f766e"),
        hovertemplate="%{x}<br>Sales: $%{y:,.0f}<extra></extra>",
    )
    return style_figure(fig, height=440)


def build_forecast_fig(monthly_sales, future_df):
    fig = px.line(
        monthly_sales,
        x="Order Date",
        y="Sales",
        markers=True,
        title="Historical and Predicted Monthly Sales",
    )
    fig.update_traces(
        name="Historical Sales",
        line=dict(color=ACCENT, width=4),
        marker=dict(size=8),
        hovertemplate="%{x}<br>Sales: $%{y:,.0f}<extra></extra>",
    )

    if not future_df.empty:
        fig.add_scatter(
            x=future_df["Forecast Month"],
            y=future_df["Upper Bound"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
        fig.add_scatter(
            x=future_df["Forecast Month"],
            y=future_df["Lower Bound"],
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(249, 115, 22, 0.16)",
            line=dict(width=0),
            name="Confidence Band",
            hoverinfo="skip",
        )
        fig.add_scatter(
            x=future_df["Forecast Month"],
            y=future_df["Predicted Sales"],
            mode="lines+markers",
            name="Predicted Sales",
            line=dict(color="#f97316", width=4, dash="dash"),
            marker=dict(size=8),
            hovertemplate="%{x}<br>Prediction: $%{y:,.0f}<extra></extra>",
        )

    return style_figure(fig, height=460)


def fig_to_png(fig):
    try:
        return fig.to_image(format="png", scale=2)
    except Exception:
        return None


def dataframe_to_csv(df):
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()


def sidebar_filters(df, source_name):
    st.sidebar.markdown("### AI BI Platform")
    st.sidebar.caption("Executive analytics workspace")

    page = st.sidebar.radio(
        "Workspace",
        [
            "Dashboard",
            "Data Quality",
            "AI Assistant",
            "Forecasting",
            "AI Reports",
            "Autonomous Insights",
            "Exports",
            "Voice Assistant",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filters")
    regions = sorted(df["Region"].dropna().unique())
    categories = sorted(df["Category"].dropna().unique())

    selected_regions = st.sidebar.multiselect("Region", options=regions, default=regions)
    selected_categories = st.sidebar.multiselect("Category", options=categories, default=categories)

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Source: {source_name}")
    st.sidebar.caption(f"{len(df):,} records loaded")

    return page, selected_regions, selected_categories


def render_upload_state():
    st.markdown('<div class="upload-shell">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Upload your CSV file",
        type=["csv"],
        help="Use a Superstore-style CSV with sales, profit, region, category, discount, order date, and order id columns.",
    )
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Try demo dataset", use_container_width=True):
            st.session_state["use_demo_data"] = True
    with col2:
        if st.button("Reset dataset", use_container_width=True):
            st.session_state["use_demo_data"] = False
            st.session_state["chat_history"] = []
    st.markdown("</div>", unsafe_allow_html=True)

    section_title("What this workspace unlocks", "A premium analytics layer for your business dataset.")
    col1, col2, col3 = st.columns(3)
    with col1:
        insight_card("Executive dashboards", "Track revenue, profit, orders, margins, trends, and category performance.")
    with col2:
        insight_card("Data quality and risks", "Scan missing values, duplicates, invalid dates, pricing issues, and anomalies.")
    with col3:
        insight_card("Exports and reports", "Download filtered data, forecasts, chart images, insights, and premium PDFs.")

    return uploaded_file


def render_dashboard(filtered_df):
    metrics = get_metrics(filtered_df)
    section_title("Executive Snapshot", "High-signal performance indicators from the active filters.")
    col1, col2, col3, col4 = st.columns(4)
    metric_items = list(metrics.items())
    for column, item in zip([col1, col2, col3, col4], metric_items[:4]):
        with column:
            metric_card(item[0], item[1], "Active filter view")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(build_category_sales_fig(filtered_df), use_container_width=True)
    with chart_col2:
        st.plotly_chart(build_region_profit_fig(filtered_df), use_container_width=True)

    section_title("Revenue Momentum", "Monthly sales trend with executive chart treatment.")
    st.plotly_chart(build_monthly_sales_fig(filtered_df), use_container_width=True)

    section_title("AI Business Signals", "Automated readouts from the current filtered dataset.")
    insights = build_advanced_insights(filtered_df)
    cols = st.columns(3)
    for index, item in enumerate(insights[:3]):
        with cols[index % 3]:
            insight_card(item["title"], item["body"])


def render_data_quality(raw_df, prepared_df, quality):
    section_title("Data Quality Scan", "Column health, invalid rows, duplicates, and readiness for analytics.")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Quality Score", f"{quality['score']}/100", "Higher is cleaner")
    with col2:
        metric_card("Missing Cells", f"{quality['missing_cells']:,}", "Across all columns")
    with col3:
        metric_card("Duplicate Rows", f"{quality['duplicate_rows']:,}", "Exact duplicates")
    with col4:
        metric_card("Valid Rows", f"{quality['clean_row_count']:,}", f"from {quality['row_count']:,} rows")

    section_title("Column Diagnostics", "Review missing values and type conversion issues.")
    diagnostics = pd.DataFrame(
        {
            "Column": raw_df.columns,
            "Missing Values": raw_df.isna().sum().values,
            "Unique Values": raw_df.nunique(dropna=True).values,
            "Data Type": raw_df.dtypes.astype(str).values,
        }
    )
    st.dataframe(diagnostics, use_container_width=True)

    issues = []
    if quality["missing_required"]:
        issues.append("Missing required columns: " + ", ".join(quality["missing_required"]))
    if quality["invalid_dates"]:
        issues.append(f"{quality['invalid_dates']:,} invalid order dates were excluded.")
    if quality["duplicate_rows"]:
        issues.append(f"{quality['duplicate_rows']:,} duplicate rows detected.")
    for column, count in quality["numeric_issues"].items():
        if count:
            issues.append(f"{column} has {count:,} non-numeric values.")

    section_title("Readiness Notes", "Actionable checks before using the dataset for decisions.")
    if issues:
        for item in issues:
            st.warning(item)
    else:
        st.success("Dataset is ready for dashboarding, AI analysis, forecasting, and reporting.")

    with st.expander("Preview cleaned data"):
        st.dataframe(prepared_df.head(50), use_container_width=True)


def render_ai_assistant(filtered_df):
    section_title("AI Business Assistant", "Chat with dataset memory during this session.")
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for message in st.session_state["chat_history"][-8:]:
        klass = "chat-bubble-user" if message["role"] == "user" else "chat-bubble-ai"
        label = "You" if message["role"] == "user" else "AI Analyst"
        st.markdown(
            f'<div class="{klass}"><strong>{label}</strong><br>{escape(message["content"])}</div>',
            unsafe_allow_html=True,
        )

    prompt = st.text_area(
        "Ask a business question",
        placeholder="Example: Which region has the weakest profit performance and what should we do next?",
        height=120,
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        analyze = st.button("Analyze with AI", use_container_width=True)
    with col2:
        if st.button("Clear chat", use_container_width=True):
            st.session_state["chat_history"] = []
            st.rerun()

    if analyze and prompt.strip():
        context = "\n".join(
            f"{item['role']}: {item['content']}" for item in st.session_state["chat_history"][-6:]
        )
        question = f"Previous conversation:\n{context}\n\nNew question:\n{prompt}"
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.spinner("AI is analyzing business performance..."):
            answer = ask_ai(question, filtered_df)
        st.session_state["chat_history"].append({"role": "assistant", "content": answer})
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render_forecasting(filtered_df):
    section_title("Sales Forecasting", "Six-month ML forecast with confidence bands.")

    if filtered_df["Order Date"].dt.to_period("M").nunique() < 2:
        st.warning("Forecasting needs at least two months of order history.")
        return None

    monthly_sales, future_df = predict_sales(filtered_df.copy())
    st.plotly_chart(build_forecast_fig(monthly_sales, future_df), use_container_width=True)
    st.dataframe(
        future_df[["Forecast Month", "Predicted Sales", "Lower Bound", "Upper Bound"]].style.format(
            {
                "Predicted Sales": "${:,.0f}",
                "Lower Bound": "${:,.0f}",
                "Upper Bound": "${:,.0f}",
            }
        ),
        use_container_width=True,
    )
    return future_df


def render_reports(filtered_df):
    section_title("AI Report Generator", "Create a premium executive report and download it as a PDF.")
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.write("The report now includes KPI tables, autonomous signals, anomalies, forecast bands, and AI narrative.")

    if st.button("Generate Executive Report", use_container_width=True):
        with st.spinner("Generating AI executive report..."):
            metrics = get_metrics(filtered_df)
            insights = build_advanced_insights(filtered_df)
            anomalies = detect_anomalies(filtered_df)
            _, forecast = predict_sales(filtered_df.copy())
            report_prompt = """
Generate a professional executive business report based on the dataset analysis.

Include:
- Executive summary
- Revenue and profit insights
- Risks and anomalies
- Forecast interpretation
- Strategic recommendations
"""
            report_text = ask_ai(report_prompt, filtered_df)
            pdf_path = generate_pdf_report(
                report_text,
                metrics=metrics,
                insights=insights,
                anomalies=anomalies,
                forecast=forecast,
            )

        st.success("Premium AI report generated successfully.")
        st.text_area("Generated AI narrative", report_text, height=320)
        with open(pdf_path, "rb") as file:
            st.download_button(
                label="Download Premium PDF Report",
                data=file,
                file_name="AI_Business_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


def render_autonomous_insights(filtered_df):
    section_title("Autonomous Insights", "Growth opportunities, profit leaks, and risk signals.")
    insights = build_advanced_insights(filtered_df)
    anomalies = detect_anomalies(filtered_df)
    legacy_insights = generate_autonomous_insights(filtered_df)

    tab1, tab2, tab3 = st.tabs(["Recommendations", "Anomalies", "Classic Engine"])
    with tab1:
        cols = st.columns(2)
        for index, item in enumerate(insights):
            with cols[index % 2]:
                insight_card(item["title"], item["body"])
    with tab2:
        cols = st.columns(2)
        for index, item in enumerate(anomalies):
            with cols[index % 2]:
                insight_card(item["title"], item["body"])
    with tab3:
        for index, item in enumerate(legacy_insights, start=1):
            insight_card(f"Signal {index}", item)


def render_exports(filtered_df):
    section_title("Export Center", "Download data, forecast, insights, charts, and reports.")
    insights = build_advanced_insights(filtered_df)
    anomalies = detect_anomalies(filtered_df)
    monthly_sales, forecast = predict_sales(filtered_df.copy())

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download filtered data CSV",
            data=dataframe_to_csv(filtered_df),
            file_name="filtered_business_data.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "Download forecast CSV",
            data=dataframe_to_csv(forecast),
            file_name="sales_forecast.csv",
            mime="text/csv",
            use_container_width=True,
        )

    insight_text = "\n".join(
        [f"- {item['title']}: {item['body']}" for item in insights + anomalies]
    )
    st.download_button(
        "Download insights summary",
        data=insight_text,
        file_name="business_insights.md",
        mime="text/markdown",
        use_container_width=True,
    )

    section_title("Chart Image Exports", "PNG exports require Kaleido, included in requirements.")
    charts = {
        "revenue_by_category.png": build_category_sales_fig(filtered_df),
        "profit_by_region.png": build_region_profit_fig(filtered_df),
        "monthly_sales_trend.png": build_monthly_sales_fig(filtered_df),
        "forecast.png": build_forecast_fig(monthly_sales, forecast),
    }
    cols = st.columns(2)
    for index, (file_name, fig) in enumerate(charts.items()):
        png = fig_to_png(fig)
        with cols[index % 2]:
            if png:
                st.download_button(
                    f"Download {file_name}",
                    data=png,
                    file_name=file_name,
                    mime="image/png",
                    use_container_width=True,
                )
            else:
                st.info(f"{file_name} export needs Kaleido installed.")

    if st.button("Generate downloadable PDF snapshot", use_container_width=True):
        report_text = "Automated executive snapshot generated from current filters."
        pdf_path = generate_pdf_report(
            report_text,
            metrics=get_metrics(filtered_df),
            insights=insights,
            anomalies=anomalies,
            forecast=forecast,
        )
        with open(pdf_path, "rb") as file:
            st.download_button(
                "Download PDF snapshot",
                data=file,
                file_name="AI_Business_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )


def render_voice_assistant():
    section_title("Voice Assistant", "Capture browser audio for voice-driven analysis workflows.")
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    audio = mic_recorder(
        start_prompt="Start Recording",
        stop_prompt="Stop Recording",
        key="voice_recorder",
    )
    if audio:
        st.success("Voice recorded successfully.")
        st.info("Browser audio captured and ready for the next voice workflow.")
    st.markdown("</div>", unsafe_allow_html=True)


def load_active_dataset(uploaded_file):
    if uploaded_file is not None:
        st.session_state["use_demo_data"] = False
        return read_csv(uploaded_file), uploaded_file.name

    if st.session_state.get("use_demo_data"):
        if not DEMO_DATA_PATH.exists():
            st.error("Demo dataset was not found in the data folder.")
            st.stop()
        return read_csv(DEMO_DATA_PATH), "Sample - Superstore.csv"

    return None, None


inject_theme()
render_hero()

uploaded_file = render_upload_state()
raw_df, source_name = load_active_dataset(uploaded_file)

if raw_df is not None:
    missing_columns = validate_dataset(raw_df)
    if missing_columns:
        st.error(
            "This CSV is missing required columns: "
            + ", ".join(missing_columns)
            + ". Please upload a Superstore-style business dataset."
        )
        st.stop()

    df = prepare_dataset(raw_df)
    if df.empty:
        st.error("No valid dated rows were found after processing the uploaded CSV.")
        st.stop()

    quality = run_data_quality_scan(raw_df, df)
    page, selected_regions, selected_categories = sidebar_filters(df, source_name)
    filtered_df = df[
        df["Region"].isin(selected_regions) & df["Category"].isin(selected_categories)
    ].copy()

    if filtered_df.empty:
        st.warning("No rows match the selected filters. Adjust the sidebar filters to continue.")
        st.stop()

    if page == "Dashboard":
        render_dashboard(filtered_df)
    elif page == "Data Quality":
        render_data_quality(raw_df, df, quality)
    elif page == "AI Assistant":
        render_ai_assistant(filtered_df)
    elif page == "Forecasting":
        render_forecasting(filtered_df)
    elif page == "AI Reports":
        render_reports(filtered_df)
    elif page == "Autonomous Insights":
        render_autonomous_insights(filtered_df)
    elif page == "Exports":
        render_exports(filtered_df)
    elif page == "Voice Assistant":
        render_voice_assistant()
