
from pathlib import Path
import pandas as pd

REQUIRED = ["open_time", "open", "high", "low", "close", "volume"]

def load_bars(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()
    if pd.api.types.is_numeric_dtype(df["open_time"]):
        unit = "ms" if df["open_time"].abs().max() > 10_000_000_000 else "s"
        df["open_time"] = pd.to_datetime(df["open_time"], unit=unit, utc=True)
    else:
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)

    df = df.sort_values("open_time").drop_duplicates("open_time").set_index("open_time")

    numeric_cols = [
        "open","high","low","close","volume","quote_volume","trades",
        "taker_buy_base","taker_buy_quote","funding_rate",
        "mark_price","index_price","open_interest"
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
