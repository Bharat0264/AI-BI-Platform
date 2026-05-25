def generate_insights(df):

    top_category = (
        df.groupby('Category')['Sales']
        .sum()
        .idxmax()
    )

    worst_region = (
        df.groupby('Region')['Profit']
        .sum()
        .idxmin()
    )

    highest_discount = df['Discount'].max()

    print("\nBUSINESS INSIGHTS")
    print("--------------------------------")

    print(f"Top Performing Category: {top_category}")

    print(f"Lowest Profit Region: {worst_region}")

    print(f"Highest Discount Offered: {highest_discount:.0%}")

    print("\nStrategic Recommendations:")

    print("- Focus marketing on high-performing categories")

    print("- Reduce heavy discount strategies")

    print("- Improve performance in weak regions")