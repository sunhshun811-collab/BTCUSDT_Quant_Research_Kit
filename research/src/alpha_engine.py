
import numpy as np
import pandas as pd

def _zscore(s: pd.Series, n: int) -> pd.Series:
    mean = s.rolling(n, min_periods=n).mean()
    std = s.rolling(n, min_periods=n).std(ddof=0)
    return (s - mean) / std.replace(0, np.nan)

def build_alpha_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Feature-only layer.
    No future values are allowed here.
    """
    out = pd.DataFrame(index=df.index)
    c = df["close"]

    # Momentum / Trend
    out["MOM_005"] = c.pct_change(5)
    out["MOM_060"] = c.pct_change(60)
    out["MOM_240"] = c.pct_change(240)

    # Mean Reversion
    out["MR_Z_020"] = -_zscore(np.log(c), 20)
    out["MR_Z_120"] = -_zscore(np.log(c), 120)

    # Volatility
    logret = np.log(c).diff()
    out["RVOL_060"] = logret.rolling(60).std(ddof=0) * np.sqrt(60)
    out["RANGE_020"] = ((df["high"] - df["low"]) / c).rolling(20).mean()

    # Order Flow
    if "taker_buy_base" in df.columns:
        vol = df["volume"].replace(0, np.nan)
        out["TAKER_IMB"] = (2.0 * df["taker_buy_base"] - df["volume"]) / vol
        out["TAKER_IMB_20"] = out["TAKER_IMB"].rolling(20).mean()

    # Perpetual basis / carry
    if {"mark_price", "index_price"}.issubset(df.columns):
        idx = df["index_price"].replace(0, np.nan)
        out["MARK_INDEX_BASIS"] = df["mark_price"] / idx - 1.0

    if "funding_rate" in df.columns:
        out["FUNDING"] = df["funding_rate"]
        out["FUNDING_Z_30"] = _zscore(df["funding_rate"], 30)

    # Positioning
    if "open_interest" in df.columns:
        out["OI_CHG_15"] = df["open_interest"].pct_change(15)
        out["OI_CHG_60"] = df["open_interest"].pct_change(60)

    return out.replace([np.inf, -np.inf], np.nan)
