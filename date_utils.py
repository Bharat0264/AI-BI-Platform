"""Deterministic, format-flexible parsing for business date columns."""
from __future__ import annotations

import pandas as pd


# ISO dates are unambiguous and take precedence.  For ambiguous numeric dates we
# retain the application's historic month-first convention; users can correct a
# semantic field when their source uses a different convention.
DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%m-%d-%Y", "%d-%m-%Y",
    "%m/%d/%Y", "%d/%m/%Y",
    "%m.%d.%Y", "%d.%m.%Y",
)


def parse_business_dates(values) -> pd.Series:
    """Parse common date formats without Pandas' mixed-format guessing warning."""
    series = values.copy() if isinstance(values, pd.Series) else pd.Series(values)
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for date_format in DATE_FORMATS:
        remaining = parsed.isna() & series.notna()
        if not remaining.any():
            break
        parsed.loc[remaining] = pd.to_datetime(series.loc[remaining], format=date_format, errors="coerce")

    # Covers ISO timestamps and named-month dates after explicit numeric formats.
    remaining = parsed.isna() & series.notna()
    if remaining.any():
        parsed.loc[remaining] = pd.to_datetime(series.loc[remaining], format="mixed", errors="coerce")
    return parsed
