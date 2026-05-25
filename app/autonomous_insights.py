def generate_autonomous_insights(df):

    insights = []


    # Region Profit Analysis
    region_profit = (
        df.groupby('Region')['Profit']
        .sum()
    )

    lowest_region = region_profit.idxmin()

    lowest_region_profit = region_profit.min()


    insights.append(
        f"Region '{lowest_region}' has the lowest profit (${lowest_region_profit:,.2f}). Consider improving operations and marketing in this region."
    )


    # Discount Risk Analysis
    avg_discount = df['Discount'].mean()

    if avg_discount > 0.15:

        insights.append(
            "High average discounts detected. Excessive discounting may reduce profitability."
        )


    # Category Performance
    category_sales = (
        df.groupby('Category')['Sales']
        .sum()
    )

    best_category = category_sales.idxmax()

    insights.append(
        f"'{best_category}' category is the top revenue generator. Focus future investments here."
    )


    # Loss Detection
    negative_profit_count = (
        df[df['Profit'] < 0]
        .shape[0]
    )

    insights.append(
        f"{negative_profit_count} transactions are generating losses."
    )


    # Sales Trend
    total_sales = df['Sales'].sum()

    if total_sales > 1000000:

        insights.append(
            "Business is generating strong overall sales performance."
        )


    return insights