def process_query(query, df):

    query = query.lower()


    # TOTAL SALES

    if "total sales" in query or "sales amount" in query:

        total_sales = df["Sales"].sum()

        return f"Total Sales: ${total_sales:,.2f}"


    # TOTAL PROFIT

    elif "total profit" in query or "overall profit" in query:

        total_profit = df["Profit"].sum()

        return f"Total Profit: ${total_profit:,.2f}"


    # TOTAL ORDERS

    elif "total orders" in query or "number of orders" in query:

        total_orders = df["Order ID"].nunique()

        return f"Total Orders: {total_orders}"


    # AVERAGE DISCOUNT

    elif "average discount" in query or "avg discount" in query:

        avg_discount = df["Discount"].mean()

        return f"Average Discount: {avg_discount:.2%}"


    # BEST CATEGORY

    elif (
        "highest sales category" in query or
        "best category" in query or
        "top category" in query
    ):

        top_category = (
            df.groupby("Category")["Sales"]
            .sum()
            .idxmax()
        )

        return f"Top Performing Category: {top_category}"


    # WORST CATEGORY

    elif "worst category" in query:

        worst_category = (
            df.groupby("Category")["Sales"]
            .sum()
            .idxmin()
        )

        return f"Worst Performing Category: {worst_category}"


    # BEST REGION

    elif (
        "highest profit region" in query or
        "best region" in query or
        "top region" in query
    ):

        best_region = (
            df.groupby("Region")["Profit"]
            .sum()
            .idxmax()
        )

        return f"Most Profitable Region: {best_region}"


    # WORST REGION

    elif (
        "lowest profit region" in query or
        "worst region" in query
    ):

        worst_region = (
            df.groupby("Region")["Profit"]
            .sum()
            .idxmin()
        )

        return f"Least Profitable Region: {worst_region}"


    # HIGHEST SALES PRODUCT

    elif (
        "top product" in query or
        "highest sales product" in query
    ):

        top_product = (
            df.groupby("Product Name")["Sales"]
            .sum()
            .idxmax()
        )

        return f"Highest Sales Product: {top_product}"


    # MOST DISCOUNTED

    elif "highest discount" in query:

        highest_discount = df["Discount"].max()

        return f"Highest Discount Given: {highest_discount:.0%}"


    # SALES BY REGION

    elif "sales by region" in query:

        sales_region = (
            df.groupby("Region")["Sales"]
            .sum()
            .to_string()
        )

        return f"Sales by Region:\n\n{sales_region}"


    # PROFIT BY CATEGORY

    elif "profit by category" in query:

        profit_category = (
            df.groupby("Category")["Profit"]
            .sum()
            .to_string()
        )

        return f"Profit by Category:\n\n{profit_category}"


    else:

        return """
Sorry, I could not understand the question.

Try asking:
- total sales
- total profit
- top category
- worst region
- top product
- sales by region
- profit by category
"""