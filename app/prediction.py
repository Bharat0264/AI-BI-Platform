import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression


def _build_features(month_index):
    month_index = pd.Series(month_index)
    return pd.DataFrame(
        {
            "Month_Index": month_index,
            "Trend_Squared": month_index**2,
            "Season_Sin": np.sin(2 * np.pi * month_index / 12),
            "Season_Cos": np.cos(2 * np.pi * month_index / 12),
        }
    )


def predict_sales(df, periods=6):
    prepared = df.copy()
    prepared["Order Date"] = pd.to_datetime(prepared["Order Date"], errors="coerce")
    prepared = prepared.dropna(subset=["Order Date"])

    monthly_sales = (
        prepared.groupby(prepared["Order Date"].dt.to_period("M"))["Sales"]
        .sum()
        .reset_index()
        .sort_values("Order Date")
    )
    monthly_sales["Order Date"] = monthly_sales["Order Date"].astype(str)
    monthly_sales["Month_Index"] = range(len(monthly_sales))

    if len(monthly_sales) < 2:
        future_df = pd.DataFrame(
            columns=[
                "Month_Index",
                "Forecast Month",
                "Predicted Sales",
                "Lower Bound",
                "Upper Bound",
            ]
        )
        return monthly_sales, future_df

    X = _build_features(monthly_sales["Month_Index"])
    y = monthly_sales["Sales"].astype(float)

    rf_model = RandomForestRegressor(
        n_estimators=250,
        min_samples_leaf=1,
        random_state=42,
    )
    trend_model = LinearRegression()

    rf_model.fit(X, y)
    trend_model.fit(monthly_sales[["Month_Index"]], y)

    future_index = range(len(monthly_sales), len(monthly_sales) + periods)
    future_features = _build_features(future_index)

    rf_predictions = rf_model.predict(future_features)
    trend_predictions = trend_model.predict(pd.DataFrame({"Month_Index": future_index}))
    predictions = (rf_predictions * 0.55) + (trend_predictions * 0.45)
    predictions = np.maximum(predictions, 0)

    fitted = (rf_model.predict(X) * 0.55) + (
        trend_model.predict(monthly_sales[["Month_Index"]]) * 0.45
    )
    residuals = np.abs(y - fitted)
    error_band = max(float(residuals.quantile(0.80)), float(y.std() * 0.15), 1.0)

    last_month = pd.Period(monthly_sales["Order Date"].iloc[-1], freq="M")
    forecast_months = [str(last_month + index) for index in range(1, periods + 1)]

    future_df = pd.DataFrame(
        {
            "Month_Index": list(future_index),
            "Forecast Month": forecast_months,
            "Predicted Sales": predictions,
            "Lower Bound": np.maximum(predictions - error_band, 0),
            "Upper Bound": predictions + error_band,
        }
    )

    return monthly_sales, future_df
