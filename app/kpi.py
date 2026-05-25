def calculate_kpis(df):

    total_sales = df['Sales'].sum()

    total_profit = df['Profit'].sum()

    total_orders = df['Order ID'].nunique()

    average_discount = df['Discount'].mean()

    print("\nKEY PERFORMANCE INDICATORS")
    print("--------------------------------")

    print(f"Total Sales: ${total_sales:,.2f}")

    print(f"Total Profit: ${total_profit:,.2f}")

    print(f"Total Orders: {total_orders}")

    print(f"Average Discount: {average_discount:.2%}")