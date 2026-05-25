import streamlit as st
import pandas as pd
import plotly.express as px
from llm_engine import ask_ai



st.set_page_config(
    page_title="AI BI Platform",
    layout="wide"
)


st.title("AI Autonomous Business Intelligence Platform")


uploaded_file = st.file_uploader(
    "Upload CSV File",
    type=["csv"]
)


if uploaded_file is not None:

    df = pd.read_csv(uploaded_file, encoding='latin1')

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

    filtered_df = df[
        (df["Region"].isin(region)) &
        (df["Category"].isin(category))
    ]

    total_sales = filtered_df["Sales"].sum()

    total_profit = filtered_df["Profit"].sum()

    total_orders = filtered_df["Order ID"].nunique()

    avg_discount = filtered_df["Discount"].mean()

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


    st.subheader("Sales by Category")

    category_sales = (
        filtered_df.groupby("Category")["Sales"]
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


    st.subheader("Profit by Region")

    region_profit = (
        filtered_df.groupby("Region")["Profit"]
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


    st.subheader("Monthly Sales Trend")

    filtered_df["Order Date"] = pd.to_datetime(
        filtered_df["Order Date"]
    )

    monthly_sales = (
        filtered_df.groupby(
            filtered_df["Order Date"].dt.to_period("M")
        )["Sales"]
        .sum()
        .reset_index()
    )

    monthly_sales["Order Date"] = (
        monthly_sales["Order Date"].astype(str)
    )

    fig3 = px.line(
        monthly_sales,
        x="Order Date",
        y="Sales",
        title="Monthly Sales Trend"
    )

    st.plotly_chart(
        fig3,
        use_container_width=True
    )


    st.subheader("Business Insights")

    top_category = (
        filtered_df.groupby("Category")["Sales"]
        .sum()
        .idxmax()
    )

    top_region = (
        filtered_df.groupby("Region")["Profit"]
        .sum()
        .idxmax()
    )

    st.success(
        f"Top Sales Category: {top_category}"
    )

    st.success(
        f"Most Profitable Region: {top_region}"
    )


    st.subheader("AI Business Assistant")

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