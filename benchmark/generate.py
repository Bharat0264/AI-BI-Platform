"""Small deterministic AURABench synthetic-family generator."""
import numpy as np
import pandas as pd

def retail(seed=42, rows=80):
    rng=np.random.default_rng(seed)
    return pd.DataFrame({"transaction_code":range(rows), "purchase_date":pd.date_range("2024-01-01",periods=rows), "gross_merchandise_value":rng.normal(500,80,rows), "net_margin":rng.normal(60,20,rows), "market":rng.choice(["North","South","West"],rows), "product_line":rng.choice(["Electronics","Home"],rows)})
