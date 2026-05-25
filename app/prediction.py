import pandas as pd

from sklearn.linear_model import LinearRegression


def predict_sales(df):

    # Convert date column
    df['Order Date'] = pd.to_datetime(
        df['Order Date']
    )


    # Monthly sales
    monthly_sales = (
        df.groupby(
            df['Order Date'].dt.to_period('M')
        )['Sales']
        .sum()
        .reset_index()
    )


    # Convert period to string
    monthly_sales['Order Date'] = (
        monthly_sales['Order Date']
        .astype(str)
    )


    # Create numerical index
    monthly_sales['Month_Index'] = range(
        len(monthly_sales)
    )


    # Features and target
    X = monthly_sales[['Month_Index']]

    y = monthly_sales['Sales']


    # Train model
    model = LinearRegression()

    model.fit(X, y)


    # Predict next 6 months
    future_index = range(
        len(monthly_sales),
        len(monthly_sales) + 6
    )


    future_df = pd.DataFrame({
        'Month_Index': future_index
    })


    predictions = model.predict(future_df)


    future_df['Predicted Sales'] = predictions


    return monthly_sales, future_df