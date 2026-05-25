import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

sns.set_style("whitegrid")


def sales_by_category(df):

    category_sales = (
        df.groupby('Category')['Sales']
        .sum()
        .reset_index()
    )

    plt.figure(figsize=(8, 5))

    sns.barplot(
        x='Category',
        y='Sales',
        data=category_sales
    )

    plt.title("Total Sales by Category")

    plt.tight_layout()

    plt.savefig("../outputs/charts/sales_by_category.png")

    plt.show()


def profit_by_region(df):

    region_profit = (
        df.groupby('Region')['Profit']
        .sum()
        .reset_index()
    )

    plt.figure(figsize=(8, 5))

    sns.barplot(
        x='Region',
        y='Profit',
        data=region_profit
    )

    plt.title("Total Profit by Region")

    plt.tight_layout()

    plt.savefig("../outputs/charts/profit_by_region.png")

    plt.show()


def monthly_sales_trend(df):

    df['Order Date'] = pd.to_datetime(df['Order Date'])

    monthly_sales = (
        df.groupby(df['Order Date'].dt.to_period('M'))['Sales']
        .sum()
    )

    monthly_sales.index = monthly_sales.index.astype(str)

    plt.figure(figsize=(12, 5))

    monthly_sales.plot()

    plt.title("Monthly Sales Trend")

    plt.xlabel("Month")

    plt.ylabel("Sales")

    plt.xticks(rotation=45)

    plt.tight_layout()

    plt.savefig("../outputs/charts/monthly_sales_trend.png")

    plt.show()


def correlation_heatmap(df):

    numeric_df = df.select_dtypes(include=['float64', 'int64'])

    plt.figure(figsize=(8, 6))

    sns.heatmap(
        numeric_df.corr(),
        annot=True,
        cmap='coolwarm'
    )

    plt.title("Correlation Heatmap")

    plt.tight_layout()

    plt.savefig("../outputs/charts/correlation_heatmap.png")

    plt.show()