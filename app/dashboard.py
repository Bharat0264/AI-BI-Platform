import streamlit as st
import pandas as pd
import plotly.express as px

from llm_engine import ask_ai
from report_generator import generate_pdf_report
from prediction import predict_sales
from autonomous_insights import (
    generate_autonomous_insights
)

from streamlit_mic_recorder import (
    mic_recorder
)


# ============================================
# PAGE CONFIG
# ============================================

st.set_page_config(
    page_title="AI BI Platform",
    page_icon="🚀",
    layout="wide"
)


# ============================================
# TITLE
# ============================================

st.title(
    "🚀 AI Autonomous Business Intelligence Platform"
)


# ============================================
# FILE UPLOAD
# ============================================

uploaded_file = st.file_uploader(
    "Upload CSV File",
    type=["csv"]
)


if uploaded_file is not None:

    # ============================================
    # LOAD DATASET
    # ============================================

    df = pd.read_csv(
        uploaded_file,
        encoding='latin1'
    )


    # ============================================
    # SIDEBAR
    # ============================================

    st.sidebar.title("Navigation")


    page = st.sidebar.radio(
        "Go To",
        [
            "🏠 Dashboard",
            "🤖 AI Assistant",
            "📈 Forecasting",
            "📄 AI Reports",
            "🧠 Autonomous Insights",
            "🎤 Voice Assistant"
        ]
    )


    st.sidebar.header("Filters")


    region = st.sidebar.multiselect(
        "Select Region",
        options=df["Region"].unique(),
        default=df["Region"].unique()
    )


    category = st.sidebar.multiselect(
        "Select Category",
        options=df["Category"].unique(),
        default=df["Category"].unique()
    )


    # ============================================
    # FILTER DATA
    # ============================================

    filtered_df = df[
        (df["Region"].isin(region)) &
        (df["Category"].isin(category))
    ]


    # ============================================
    # DASHBOARD PAGE
    # ============================================

    if page == "🏠 Dashboard":

        st.header("Business Dashboard")


        # KPIs
        total_sales = filtered_df["Sales"].sum()

        total_profit = filtered_df["Profit"].sum()

        total_orders = filtered_df[
            "Order ID"
        ].nunique()

        avg_discount = filtered_df[
            "Discount"
        ].mean()


        col1, col2, col3, col4 = st.columns(4)


        col1.metric(
            "Total Sales",
            f"${total_sales:,.0f}"
        )


        col2.metric(
            "Total Profit",
            f"${total_profit:,.0f}"
        )


        col3.metric(
            "Orders",
            total_orders
        )


        col4.metric(
            "Avg Discount",
            f"{avg_discount:.0%}"
        )


        # Sales by Category
        st.subheader(
            "Sales by Category"
        )


        category_sales = (
            filtered_df.groupby(
                "Category"
            )["Sales"]
            .sum()
            .reset_index()
        )


        fig1 = px.bar(
            category_sales,
            x="Category",
            y="Sales",
            color="Category",
            title="Sales by Category"
        )


        st.plotly_chart(
            fig1,
            use_container_width=True
        )


        # Profit by Region
        st.subheader(
            "Profit by Region"
        )


        region_profit = (
            filtered_df.groupby(
                "Region"
            )["Profit"]
            .sum()
            .reset_index()
        )


        fig2 = px.bar(
            region_profit,
            x="Region",
            y="Profit",
            color="Region",
            title="Profit by Region"
        )


        st.plotly_chart(
            fig2,
            use_container_width=True
        )


        # Monthly Sales Trend
        st.subheader(
            "Monthly Sales Trend"
        )


        filtered_df["Order Date"] = (
            pd.to_datetime(
                filtered_df["Order Date"]
            )
        )


        monthly_sales_chart = (
            filtered_df.groupby(
                filtered_df[
                    "Order Date"
                ].dt.to_period("M")
            )["Sales"]
            .sum()
            .reset_index()
        )


        monthly_sales_chart["Order Date"] = (
            monthly_sales_chart[
                "Order Date"
            ].astype(str)
        )


        fig3 = px.line(
            monthly_sales_chart,
            x="Order Date",
            y="Sales",
            title="Monthly Sales Trend"
        )


        st.plotly_chart(
            fig3,
            use_container_width=True
        )


        # Business Insights
        st.subheader(
            "Business Insights"
        )


        top_category = (
            filtered_df.groupby(
                "Category"
            )["Sales"]
            .sum()
            .idxmax()
        )


        top_region = (
            filtered_df.groupby(
                "Region"
            )["Profit"]
            .sum()
            .idxmax()
        )


        st.success(
            f"Top Sales Category: {top_category}"
        )


        st.success(
            f"Most Profitable Region: {top_region}"
        )


    # ============================================
    # AI ASSISTANT PAGE
    # ============================================

    elif page == "🤖 AI Assistant":

        st.header(
            "AI Business Assistant"
        )


        user_query = st.text_input(
            "Ask Any Business Question"
        )


        if user_query:

            with st.spinner(
                "AI is analyzing business data..."
            ):

                answer = ask_ai(
                    user_query,
                    filtered_df
                )

            st.success(answer)


    # ============================================
    # FORECASTING PAGE
    # ============================================

    elif page == "📈 Forecasting":

        st.header(
            "Sales Forecasting"
        )


        monthly_sales, future_df = (
            predict_sales(
                filtered_df
            )
        )


        forecast_chart = px.line(
            monthly_sales,
            x='Order Date',
            y='Sales',
            title='Historical Monthly Sales'
        )


        forecast_chart.add_scatter(
            x=future_df['Month_Index'],
            y=future_df[
                'Predicted Sales'
            ],
            mode='lines+markers',
            name='Predicted Sales'
        )


        st.plotly_chart(
            forecast_chart,
            use_container_width=True
        )


        st.dataframe(
            future_df
        )


    # ============================================
    # AI REPORTS PAGE
    # ============================================

    elif page == "📄 AI Reports":

        st.header(
            "AI Report Generator"
        )


        if st.button(
            "Generate AI Report"
        ):

            with st.spinner(
                "Generating AI Executive Report..."
            ):

                report_prompt = """
Generate a professional business report
based on the dataset analysis.

Include:
- Executive summary
- Business insights
- Problems detected
- Recommendations
- Strategic suggestions
"""


                report_text = ask_ai(
                    report_prompt,
                    filtered_df
                )


                pdf_path = (
                    generate_pdf_report(
                        report_text
                    )
                )


                st.success(
                    "AI Report Generated Successfully!"
                )


                st.text_area(
                    "Generated Report",
                    report_text,
                    height=300
                )


                with open(
                    pdf_path,
                    "rb"
                ) as file:

                    st.download_button(
                        label="Download PDF Report",
                        data=file,
                        file_name=(
                            "AI_Business_Report.pdf"
                        ),
                        mime="application/pdf"
                    )


    # ============================================
    # AUTONOMOUS INSIGHTS PAGE
    # ============================================

    elif page == "🧠 Autonomous Insights":

        st.header(
            "Autonomous AI Insights"
        )


        autonomous_insights = (
            generate_autonomous_insights(
                filtered_df
            )
        )


        for insight in autonomous_insights:

            st.warning(insight)


    # ============================================
    # VOICE ASSISTANT PAGE
    # ============================================

    elif page == "🎤 Voice Assistant":

        st.header(
            "Browser Voice Assistant"
        )


        audio = mic_recorder(
            start_prompt="Start Recording",
            stop_prompt="Stop Recording",
            key='voice_recorder'
        )


        if audio:

            st.success(
                "Voice recorded successfully!"
            )

            st.info(
                "Browser audio captured."
            )