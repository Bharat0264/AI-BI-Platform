"""Semantic normalization for common business datasets."""
import re
import pandas as pd
from date_utils import parse_business_dates

ALIASES = {
    "Order ID": ["order id", "order_id", "invoice id", "invoice", "transaction id"],
    "Order Date": ["order date", "order_date", "date", "transaction date", "invoice date", "timestamp"],
    "Region": ["region", "market", "state", "country", "territory", "location", "city"],
    "Category": ["category", "product category", "department", "industry", "type", "product line"],
    "Product Name": ["product name", "product", "item", "item name", "sku", "commodity", "crop"],
    "Quantity": ["quantity", "qty", "units", "units sold", "volume", "demand"],
    "Inventory": ["inventory", "stock", "stock on hand", "on hand", "available stock", "closing stock"],
    "Sales": ["sales", "revenue", "amount", "total", "turnover", "net sales", "price"],
    "Profit": ["profit", "net profit", "gross profit", "income", "margin", "earnings"],
    "Discount": ["discount", "discount rate", "discount percent", "markdown"],
}

def _key(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()

def normalize_business_dataset(df):
    if df.empty:
        raise ValueError("The dataset has no rows.")
    result, mapping, used = df.copy(), {}, set()
    keyed = {_key(col): col for col in result.columns}
    for target, aliases in ALIASES.items():
        source = next((keyed[_key(a)] for a in aliases if _key(a) in keyed and keyed[_key(a)] not in used), None)
        if source:
            mapping[target], used = source, used | {source}
    if "Order Date" not in mapping:
        for col in result.select_dtypes(include=["object"]).columns:
            if parse_business_dates(result[col]).notna().mean() >= .8:
                mapping["Order Date"], used = col, used | {col}; break
    numeric = [c for c in result.columns if pd.to_numeric(result[c], errors="coerce").notna().mean() >= .8]
    if "Sales" not in mapping:
        source = next((c for c in numeric if c not in used), None)
        if source: mapping["Sales"], used = source, used | {source}
    if "Order Date" not in mapping or "Sales" not in mapping:
        raise ValueError("This does not look like a time-based business dataset. Include a date and numeric sales/revenue/amount column.")
    for target, source in mapping.items():
        if target != source: result[target] = result[source]
    warnings = []
    if "Profit" not in mapping:
        cost = next((c for c in result.columns if _key(c) in {"cost", "expenses", "total cost", "cogs"}), None)
        result["Profit"] = pd.to_numeric(result["Sales"], errors="coerce") - pd.to_numeric(result[cost], errors="coerce") if cost else 0.0
        warnings.append("Profit derived from sales minus cost." if cost else "Profit not supplied; profit analytics show zero.")
    if "Discount" not in mapping: result["Discount"] = 0.0; warnings.append("Discount not supplied; discount analytics use zero.")
    if "Region" not in mapping: result["Region"] = "All business"
    if "Category" not in mapping:
        text = next((c for c in result.select_dtypes(include=["object"]).columns if c not in used), None)
        result["Category"] = result[text].fillna("Uncategorized") if text else "Uncategorized"
    if "Order ID" not in mapping: result["Order ID"] = [f"ROW-{i+1}" for i in range(len(result))]
    if "Product Name" not in mapping: result["Product Name"] = result["Category"]
    if "Quantity" not in mapping:
        result["Quantity"] = 1.0
        warnings.append("Quantity not supplied; demand planning treats each row as one unit. Add a quantity/units column for stock recommendations.")
    return result, mapping, warnings
