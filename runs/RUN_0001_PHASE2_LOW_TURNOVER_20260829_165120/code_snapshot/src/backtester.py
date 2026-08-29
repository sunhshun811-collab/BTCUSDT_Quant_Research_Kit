
import numpy as np
import pandas as pd
from .metrics import performance_metrics, information_coefficient

def robust_zscore_signal(feature: pd.Series, lookback: int = 240, clip: float = 3.0) -> pd.Series:
    mu = feature.rolling(lookback, min_periods=lookback).mean()
    sd = feature.rolling(lookback, min_periods=lookback).std(ddof=0).replace(0, np.nan)
    z = ((feature - mu) / sd).clip(-clip, clip)
    return (z / clip).fillna(0.0)

def backtest_feature(
    close: pd.Series,
    feature: pd.Series,
    fee_bps_one_way: float = 5.0,
    slippage_bps_one_way: float = 1.0,
) -> dict:
    # Position at t uses feature information known at t-1.
    raw = robust_zscore_signal(feature)
    position = raw.shift(1).fillna(0.0)

    ret = close.pct_change().fillna(0.0)
    turnover = position.diff().abs().fillna(position.abs())
    cost_rate = (fee_bps_one_way + slippage_bps_one_way) / 10_000.0
    cost = turnover * cost_rate
    strategy_ret = position * ret - cost

    fwd_ret = close.pct_change().shift(-1)
    perf = performance_metrics(strategy_ret)
    perf.update(information_coefficient(feature, fwd_ret))
    perf["avg_turnover_per_bar"] = float(turnover.mean())

    return {
        "position": position,
        "strategy_return": strategy_ret,
        "metrics": perf,
    }
