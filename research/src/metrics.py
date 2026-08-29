
import numpy as np
import pandas as pd

MINUTES_PER_YEAR = 365.25 * 24 * 60

def performance_metrics(ret: pd.Series) -> dict:
    r = ret.dropna()
    if len(r) == 0:
        return {}
    equity = (1 + r).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1
    mu, sd = r.mean(), r.std(ddof=0)
    sharpe = float(mu / sd * np.sqrt(MINUTES_PER_YEAR)) if sd > 0 else 0.0
    downside = r[r < 0].std(ddof=0)
    sortino = float(mu / downside * np.sqrt(MINUTES_PER_YEAR)) if downside and downside > 0 else 0.0
    return {
        "bars": int(len(r)),
        "total_return": float(equity.iloc[-1] - 1),
        "annualized_sharpe": sharpe,
        "annualized_sortino": sortino,
        "max_drawdown": float(dd.min()),
        "win_rate": float((r > 0).mean()),
    }

def information_coefficient(signal: pd.Series, fwd_ret: pd.Series) -> dict:
    x = pd.concat([signal.rename("s"), fwd_ret.rename("r")], axis=1).dropna()
    if len(x) < 3:
        return {"ic": None, "rank_ic": None}
    return {
        "ic": float(x["s"].corr(x["r"])),
        "rank_ic": float(x["s"].rank().corr(x["r"].rank())),
    }
