import os

from data_loader import load_data
from cleaning import clean_data
from eda import perform_eda
from visualization import sales_by_category
from visualization import profit_by_region
from visualization import monthly_sales_trend
from visualization import correlation_heatmap
from insights import generate_insights
from kpi import calculate_kpis


def main():

    base_dir = os.path.dirname(__file__)

    csv_path = os.path.join(
        base_dir,
        "..",
        "data",
        "Sample - Superstore.csv"
    )

    df = load_data(csv_path)

    if df is not None:

        df = clean_data(df)

        perform_eda(df)

        calculate_kpis(df)

        sales_by_category(df)

        profit_by_region(df)

        monthly_sales_trend(df)

        correlation_heatmap(df)

        generate_insights(df)


if __name__ == "__main__":
    main()