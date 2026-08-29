from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import gc
import json
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FeatureSpec:
    alpha_id: str
    family: str
    hypothesis: str
    rebalance_minutes: int
    smoothing_halflife_minutes: int
    no_trade_band: float
    feature: pd.Series


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0).replace(0.0, np.nan)
    return (series - mean) / std


def _safe_log(series: pd.Series) -> pd.Series:
    return np.log(series.astype(float).where(series > 0.0))


def load_visible_data(data_path: Path, config: dict) -> pd.DataFrame:
    columns = [
        "open_time", "open", "high", "low", "close", "volume", "quote_volume", "trades",
        "taker_buy_base", "btc_spot_close", "eth_spot_close",
        "funding_rate", "funding_event",
    ]
    start = pd.Timestamp(config["research_start"])
    validation_end = pd.Timestamp(config["validation_end"])
    try:
        df = pd.read_parquet(
            data_path,
            columns=columns,
            filters=[("open_time", ">=", start),
                     ("open_time", "<", validation_end)],
        )
    except Exception:
        # Older pandas/pyarrow combinations may not support timezone-aware filters.
        # The hard lock below is always applied again after loading.
        df = pd.read_parquet(data_path, columns=columns)

    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    df = df.set_index("open_time").sort_index()
    df = df[(df.index >= start) & (df.index < validation_end)].copy()

    if df.empty:
        raise ValueError("No Train/Validation rows were loaded.")
    if df.index.max() >= validation_end:
        raise AssertionError("TEST LOCK FAILED: a test timestamp became visible.")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError("open_time must be unique and strictly ordered.")
    return df


def iter_feature_specs(df: pd.DataFrame):
    log_close = _safe_log(df["close"])
    ret_1m = log_close.diff()
    volume = df["volume"].astype(float).replace(0.0, np.nan)
    quote_volume = df["quote_volume"].astype(float).replace(0.0, np.nan)
    trades = df["trades"].astype(float).replace(0.0, np.nan)
    taker_imbalance = (2.0 * df["taker_buy_base"].astype(float) - volume) / volume

    def spec(alpha_id, family, hypothesis, rebalance, smooth, band, feature):
        clean = feature.replace([np.inf, -np.inf], np.nan).astype("float32")
        return FeatureSpec(alpha_id, family, hypothesis, rebalance, smooth, band, clean)

    for horizon in (240, 720, 1440, 4320):
        yield spec(
            f"LT_MOM_{horizon:04d}", "Momentum / Trend",
            f"{horizon}m persistence may survive when traded slowly.",
            60, 240, 0.15, log_close.diff(horizon),
        )

    for window in (240, 1440):
        yield spec(
            f"LT_MR_Z_{window:04d}", "Mean Reversion",
            f"Price dislocation over {window}m may mean revert after turnover control.",
            30 if window == 240 else 60, 120 if window == 240 else 360, 0.15,
            -rolling_zscore(log_close, window),
        )

    for window in (240, 720):
        yield spec(
            f"LT_OFI_{window:04d}", "Order Flow",
            f"Persistent taker imbalance over {window}m may identify informed pressure.",
            15 if window == 240 else 30, 60 if window == 240 else 180, 0.12,
            taker_imbalance.rolling(window, min_periods=window).mean(),
        )

    rv_720 = ret_1m.rolling(720, min_periods=720).std(ddof=0)
    yield spec(
        "LT_VOL_ADJ_MOM_0720", "Volatility",
        "Risk-scaled 12h momentum may be more stable across volatility regimes.",
        60, 240, 0.15,
        log_close.diff(720) / (rv_720 * math.sqrt(720.0)).replace(0.0, np.nan),
    )

    volume_z = rolling_zscore(np.log1p(quote_volume), 1440)
    yield spec(
        "LT_VOLUME_CONFIRMED_MOM_0720", "Liquidity / Microstructure",
        "12h momentum with above-normal dollar volume may have stronger continuation.",
        60, 240, 0.15,
        log_close.diff(720) * volume_z.clip(lower=0.0, upper=3.0),
    )

    amihud = ret_1m.abs() / quote_volume
    yield spec(
        "LT_ILLIQ_MR_1440", "Liquidity / Microstructure",
        "One-day extreme price impact may normalize when positions change slowly.",
        60, 360, 0.18,
        -rolling_zscore(np.log1p(amihud * 1e9), 10080),
    )

    avg_trade = quote_volume / trades
    trade_size_z = rolling_zscore(np.log1p(avg_trade), 1440)
    yield spec(
        "LT_TRADE_SIZE_DIR_0240", "Liquidity / Microstructure",
        "Large average trade-size shocks may confirm the prevailing 4h direction.",
        30, 120, 0.15,
        trade_size_z * np.sign(log_close.diff(240)),
    )

    if "funding_rate" in df.columns:
        funding = df["funding_rate"].astype(float)
        yield spec(
            "LT_FUNDING_CROWDING_MR_30D", "Carry / Funding",
            "Thirty-day funding extremes may proxy crowded perpetual positioning.",
            60, 720, 0.12,
            -rolling_zscore(funding, 30 * 24 * 60),
        )

    if "btc_spot_close" in df.columns:
        spot_log = _safe_log(df["btc_spot_close"].ffill())
        basis = log_close - spot_log
        for window in (10080, 43200):
            yield spec(
                f"LT_PERP_SPOT_BASIS_MR_{window:05d}", "Relative Value",
                f"Perpetual/spot basis dislocation over {window}m may mean revert.",
                60, 720, 0.12,
                -rolling_zscore(basis, window),
            )

    if "btc_spot_close" in df.columns and "eth_spot_close" in df.columns:
        btc_log = _safe_log(df["btc_spot_close"].ffill())
        eth_log = _safe_log(df["eth_spot_close"].ffill())
        ratio = btc_log - eth_log
        yield spec(
            "LT_BTC_ETH_RATIO_MR_7D", "Relative Value",
            "Extreme BTC/ETH log-price ratio deviations may mean revert.",
            60, 720, 0.12,
            -rolling_zscore(ratio, 10080),
        )
        yield spec(
            "LT_BTC_ETH_RATIO_MOM_1D", "Relative Value",
            "One-day BTC relative strength versus ETH may persist at a slower horizon.",
            60, 360, 0.15,
            ratio.diff(1440),
        )


def build_position(
    feature: pd.Series,
    normalization_lookback: int,
    clip_z: float,
    rebalance_minutes: int,
    smoothing_halflife: int,
    no_trade_band: float,
    position_step: float,
    position_cap: float,
    return_trace: bool = False,
):
    normalized = rolling_zscore(feature.astype(float), normalization_lookback)
    desired = (normalized.clip(-clip_z, clip_z) / clip_z).clip(-position_cap, position_cap)

    # A position used for bar t is derived only from information through t-1.
    # The fixed single-alpha execution layer therefore executes any state change
    # at bar t OPEN, never at bar t CLOSE.
    lagged = desired.shift(1).fillna(0.0)
    smoothed = lagged.ewm(
        halflife=max(int(smoothing_halflife), 1), adjust=False, min_periods=1
    ).mean()

    rebalance_minutes = max(int(rebalance_minutes), 1)
    targets = smoothed.iloc[::rebalance_minutes]
    states = np.empty(len(targets), dtype=np.float32)
    current = 0.0
    for i, target in enumerate(targets.to_numpy(dtype=float)):
        if np.isfinite(target) and abs(target - current) >= no_trade_band:
            current = float(np.clip(
                np.round(target / position_step) * position_step,
                -position_cap,
                position_cap,
            ))
        states[i] = current

    sparse = pd.Series(states, index=targets.index)
    position = sparse.reindex(feature.index, method="ffill").fillna(0.0).astype("float32")
    if not return_trace:
        return position

    trace_index = targets.index
    trace = pd.DataFrame({
        "zscore": normalized.reindex(trace_index).astype("float32"),
        "smoothed_target": smoothed.reindex(trace_index).astype("float32"),
        "variable_position": position.reindex(trace_index).astype("float32"),
    }, index=trace_index)
    trace["fixed_state"] = np.sign(trace["variable_position"]).astype("float32")
    return position, trace


def daily_metrics(returns: pd.Series, position: pd.Series, gross: pd.Series) -> dict:
    returns = returns.dropna()
    if returns.empty:
        return {}
    daily = returns.resample("1D").sum().dropna()
    daily_sd = daily.std(ddof=1)
    sharpe = float(daily.mean() / daily_sd * math.sqrt(365.25)) if daily_sd > 0 else 0.0
    equity = (1.0 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    turnover = position.diff().abs().fillna(position.abs())
    turnover_sum = float(turnover.sum())
    gross_sum = float(gross.sum())
    return {
        "bars": int(len(returns)),
        "net_return": float(equity.iloc[-1] - 1.0),
        "net_sharpe_daily": sharpe,
        "max_drawdown": float(drawdown.min()),
        "avg_turnover_per_bar": float(turnover.mean()),
        "annualized_turnover": float(turnover.resample("1D").sum().mean() * 365.25),
        "trade_events": int((turnover > 0.0).sum()),
        "mean_abs_position": float(position.abs().mean()),
        "gross_bps_per_unit_turnover": (
            float(gross_sum / turnover_sum * 10000.0) if turnover_sum > 0 else np.nan
        ),
    }


def predictive_metrics(
    feature: pd.Series,
    close: pd.Series,
    mask: pd.Series,
    horizons: list[int],
    sample_every: int,
) -> dict:
    out = {}
    sampled_feature = feature[mask].iloc[::sample_every].astype(float)
    for horizon in horizons:
        fwd = (close.shift(-horizon) / close - 1.0)[mask].iloc[::sample_every]
        pair = pd.concat([sampled_feature.rename("f"), fwd.rename("r")], axis=1).dropna()
        if len(pair) < 100:
            out[f"ic_{horizon}m"] = np.nan
            out[f"rank_ic_{horizon}m"] = np.nan
        else:
            out[f"ic_{horizon}m"] = float(pair["f"].corr(pair["r"]))
            out[f"rank_ic_{horizon}m"] = float(pair["f"].rank().corr(pair["r"].rank()))
    return out


def _strategy_components(
    df: pd.DataFrame,
    position: pd.Series,
    include_funding: bool,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    market_return = df["close"].astype(float).pct_change().fillna(0.0)
    price_pnl = position.astype(float) * market_return
    funding_pnl = pd.Series(0.0, index=df.index)
    if include_funding and {"funding_rate", "funding_event"}.issubset(df.columns):
        event_rate = df["funding_rate"].astype(float).where(df["funding_event"].fillna(False), 0.0)
        # Positive funding means longs pay shorts.
        funding_pnl = -position.astype(float) * event_rate.fillna(0.0)
    gross = price_pnl + funding_pnl
    turnover = position.diff().abs().fillna(position.abs()).astype(float)
    return gross, turnover, funding_pnl


def _json_value(value):
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    return value



def _annualized_sharpe_daily(returns: pd.Series) -> float:
    daily = returns.dropna().resample("1D").apply(lambda x: (1.0 + x).prod() - 1.0).dropna()
    if len(daily) < 2:
        return np.nan
    sd = daily.std(ddof=1)
    return float(daily.mean() / sd * math.sqrt(365.25)) if sd > 0 else 0.0


def _simple_strategy_metrics(returns: pd.Series, state: pd.Series) -> dict:
    returns = returns.dropna()
    if returns.empty:
        return {}
    equity = (1.0 + returns).cumprod()
    dd = equity / equity.cummax() - 1.0
    daily = returns.resample("1D").apply(lambda x: (1.0 + x).prod() - 1.0).dropna()
    sd = daily.std(ddof=1)
    sh = float(daily.mean() / sd * math.sqrt(365.25)) if len(daily) > 1 and sd > 0 else 0.0
    s = state.reindex(returns.index).fillna(0.0).astype(float)
    prev = s.shift(1).fillna(0.0)
    entries = ((s != 0.0) & (s != prev)).sum()
    turnover = (s - prev).abs()
    return {
        "bars": int(len(returns)),
        "net_return": float(equity.iloc[-1] - 1.0),
        "net_sharpe_daily": sh,
        "max_drawdown": float(dd.min()),
        "trade_entries": int(entries),
        "time_in_market": float((s != 0.0).mean()),
        "annualized_turnover": float(turnover.resample("1D").sum().mean() * 365.25),
    }


def _beta_metrics(strategy_returns: pd.Series, df: pd.DataFrame, mask: pd.Series) -> dict:
    """Descriptive daily multi-factor OLS exposure diagnostics."""
    s = strategy_returns[mask].astype(float)
    out = {
        "beta_btc_daily": np.nan,
        "beta_eth_daily": np.nan,
        "beta_r2_daily": np.nan,
        "residual_sharpe_daily": np.nan,
        "alpha_intercept_ann": np.nan,
        "corr_btc_1m": np.nan,
        "corr_eth_1m": np.nan,
    }
    if s.empty:
        return out

    factors = {}
    if "btc_spot_close" in df.columns:
        btc = df["btc_spot_close"].astype(float).ffill().pct_change()
        factors["btc"] = btc[mask]
        pair = pd.concat([s.rename("s"), factors["btc"].rename("m")], axis=1).dropna()
        if len(pair) >= 100 and pair["s"].std(ddof=0) > 0 and pair["m"].std(ddof=0) > 0:
            out["corr_btc_1m"] = float(pair["s"].corr(pair["m"]))
    if "eth_spot_close" in df.columns:
        eth = df["eth_spot_close"].astype(float).ffill().pct_change()
        factors["eth"] = eth[mask]
        pair = pd.concat([s.rename("s"), factors["eth"].rename("m")], axis=1).dropna()
        if len(pair) >= 100 and pair["s"].std(ddof=0) > 0 and pair["m"].std(ddof=0) > 0:
            out["corr_eth_1m"] = float(pair["s"].corr(pair["m"]))

    y = s.resample("1D").apply(lambda x: (1.0 + x).prod() - 1.0).rename("strategy")
    cols, names = [y], []
    for key, values in factors.items():
        cols.append(values.resample("1D").sum().rename(key))
        names.append(key)
    reg = pd.concat(cols, axis=1).dropna()
    if len(reg) < 30 or not names:
        return out

    yv = reg["strategy"].to_numpy(dtype=float)
    Xf = reg[names].to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(reg)), Xf])
    coef, *_ = np.linalg.lstsq(X, yv, rcond=None)
    pred = X @ coef
    resid = yv - pred
    ss_tot = float(np.sum((yv - yv.mean()) ** 2))
    ss_res = float(np.sum(resid ** 2))
    out["beta_r2_daily"] = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    out["alpha_intercept_ann"] = float(coef[0] * 365.25)
    resid_s = pd.Series(resid, index=reg.index)
    sd = resid_s.std(ddof=1)
    out["residual_sharpe_daily"] = float(resid_s.mean() / sd * math.sqrt(365.25)) if sd > 0 else 0.0
    if "btc" in names:
        out["beta_btc_daily"] = float(coef[1 + names.index("btc")])
    if "eth" in names:
        out["beta_eth_daily"] = float(coef[1 + names.index("eth")])
    return out


def _simple_beta(strategy: pd.Series, benchmark: pd.Series, mask: pd.Series) -> float:
    pair = pd.concat([strategy[mask].rename("s"), benchmark[mask].rename("b")], axis=1).dropna()
    if len(pair) < 100:
        return np.nan
    var = float(pair["b"].var(ddof=0))
    if var <= 0:
        return np.nan
    return float(pair["s"].cov(pair["b"], ddof=0) / var)


def _rolling_beta_array(s: np.ndarray, b: np.ndarray, window: int) -> np.ndarray:
    n = len(s)
    out = np.full(n, np.nan, dtype=np.float64)
    if n < window or window < 2:
        return out
    valid = np.isfinite(s) & np.isfinite(b)
    sx = np.where(valid, s, 0.0)
    bx = np.where(valid, b, 0.0)
    c = valid.astype(np.float64)
    def rollsum(x):
        cs = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])
        return cs[window:] - cs[:-window]
    cnt = rollsum(c)
    ss = rollsum(sx)
    bb = rollsum(bx)
    sb = rollsum(sx * bx)
    b2 = rollsum(bx * bx)
    denom = b2 - bb * bb / np.maximum(cnt, 1.0)
    numer = sb - ss * bb / np.maximum(cnt, 1.0)
    beta = np.where((cnt >= window * 0.8) & (denom > 1e-18), numer / denom, np.nan)
    out[window - 1:] = beta
    return out


def _beta_profile_rows(alpha_id: str, strategy_returns: pd.Series, df: pd.DataFrame,
                       train: pd.Series, validation: pd.Series,
                       windows_minutes: list[int]) -> list[dict]:
    """Rolling beta profile on 5-minute observations to reduce 1m noise/cost."""
    s5 = strategy_returns.resample("5min").apply(lambda x: (1.0 + x).prod() - 1.0)
    rows = []
    benchmarks = {}
    if "btc_spot_close" in df.columns:
        benchmarks["BTC_SPOT"] = df["btc_spot_close"].astype(float).ffill().resample("5min").last().pct_change()
    if "eth_spot_close" in df.columns:
        benchmarks["ETH_SPOT"] = df["eth_spot_close"].astype(float).ffill().resample("5min").last().pct_change()
    if not benchmarks:
        return rows

    train5 = pd.Series(s5.index < train.index[train].max() + pd.Timedelta(minutes=1), index=s5.index)
    val_start = train.index[train].max() + pd.Timedelta(minutes=1)
    val_end = validation.index[validation].max() + pd.Timedelta(minutes=1)
    val5 = pd.Series((s5.index >= val_start) & (s5.index < val_end), index=s5.index)
    for name, bench in benchmarks.items():
        aligned = pd.concat([s5.rename("s"), bench.rename("b")], axis=1).dropna()
        for minutes in windows_minutes:
            w = max(2, int(round(minutes / 5)))
            beta = _rolling_beta_array(aligned["s"].to_numpy(float), aligned["b"].to_numpy(float), w)
            beta_s = pd.Series(beta, index=aligned.index)
            for segment_name, segmask in (("train", train5), ("validation", val5)):
                vals = beta_s.reindex(segmask.index)[segmask].dropna()
                if vals.empty:
                    stats = dict(mean=np.nan, std=np.nan, p05=np.nan, p95=np.nan)
                else:
                    stats = dict(mean=float(vals.mean()), std=float(vals.std(ddof=0)),
                                 p05=float(vals.quantile(.05)), p95=float(vals.quantile(.95)))
                rows.append({"alpha_id": alpha_id, "segment": segment_name, "benchmark": name,
                             "window_minutes": int(minutes), "sampling_minutes": 5, **stats})
    return rows


def _regime_beta_metrics(strategy_returns: pd.Series, df: pd.DataFrame, mask: pd.Series) -> dict:
    out = {"btc_beta_bull": np.nan, "btc_beta_bear": np.nan,
           "btc_beta_high_vol": np.nan, "btc_beta_low_vol": np.nan}
    if "btc_spot_close" not in df.columns:
        return out
    spot = df["btc_spot_close"].astype(float).ffill()
    b = spot.pct_change().fillna(0.0)
    trend = spot / spot.shift(1440) - 1.0
    vol = b.rolling(1440, min_periods=720).std(ddof=0)
    vol_med = vol.rolling(10080, min_periods=1440).median()
    out["btc_beta_bull"] = _simple_beta(strategy_returns, b, mask & (trend >= 0))
    out["btc_beta_bear"] = _simple_beta(strategy_returns, b, mask & (trend < 0))
    out["btc_beta_high_vol"] = _simple_beta(strategy_returns, b, mask & (vol >= vol_med))
    out["btc_beta_low_vol"] = _simple_beta(strategy_returns, b, mask & (vol < vol_med))
    return out


def _direction_type_from_train(long_sharpe, short_sharpe, asymmetry_ratio: float) -> tuple[str, str]:
    l = float(long_sharpe) if np.isfinite(long_sharpe) else -np.inf
    s = float(short_sharpe) if np.isfinite(short_sharpe) else -np.inf
    if l > 0 and s > 0:
        small = min(abs(l), abs(s))
        ratio = max(abs(l), abs(s)) / small if small > 1e-12 else np.inf
        dominant = "LONG" if l >= s else "SHORT"
        return ("ASYMMETRIC_LS" if ratio >= asymmetry_ratio else "LONG_SHORT", dominant)
    if l > 0 and s <= 0:
        return "LONG_ONLY", "LONG"
    if s > 0 and l <= 0:
        return "SHORT_ONLY", "SHORT"
    return "UNRESOLVED", "NONE"


def _fixed_state(variable_position: pd.Series) -> pd.Series:
    return pd.Series(np.sign(variable_position.to_numpy(dtype=float)), index=variable_position.index, dtype="float32")


def _fixed_single_alpha_simulation(
    df: pd.DataFrame,
    state: pd.Series,
    cost_bps_one_way: float,
    include_funding: bool,
    margin_fraction: float,
    leverage: float,
    train_end: pd.Timestamp,
    record_trades: bool = True,
) -> dict:
    """Fixed one-alpha execution model.

    Rules:
    - one alpha only;
    - 10% isolated margin per trade;
    - 10x leverage;
    - notional at entry = 100% of account equity;
    - no pyramiding or partial resizing while sign is unchanged;
    - state change known from t-1 information executes at bar t OPEN.

    Liquidation is NOT simulated exactly because historical Mark Price and maintenance
    margin tiers are absent. Intrabar High/Low is used for a conservative 10x margin
    stress proxy.
    """
    margin_fraction = float(margin_fraction)
    leverage = float(leverage)
    notional_fraction = margin_fraction * leverage
    if abs(margin_fraction - 0.10) > 1e-12 or abs(leverage - 10.0) > 1e-12:
        raise ValueError("Fixed single-alpha model requires 10% margin and 10x leverage.")
    if abs(notional_fraction - 1.0) > 1e-12:
        raise AssertionError("Expected entry notional to equal 100% of account equity.")

    idx = df.index
    n = len(df)
    s = np.sign(state.reindex(idx).fillna(0.0).to_numpy(dtype=float)).astype(np.int8)
    op = df["open"].to_numpy(dtype=float)
    hi = df["high"].to_numpy(dtype=float)
    lo = df["low"].to_numpy(dtype=float)
    cl = df["close"].to_numpy(dtype=float)
    fr = df["funding_rate"].fillna(0.0).to_numpy(dtype=float) if "funding_rate" in df.columns else np.zeros(n)
    fe = df["funding_event"].fillna(False).to_numpy(dtype=bool) if "funding_event" in df.columns else np.zeros(n, dtype=bool)
    cost = float(cost_bps_one_way) / 10000.0

    # Constant-state segments [start, end).
    boundaries = np.flatnonzero(np.r_[True, s[1:] != s[:-1], True])
    equity_close = np.full(n, np.nan, dtype=np.float64)
    account_equity = 1.0
    trades, events = [], []
    trade_no = 0

    for k in range(len(boundaries) - 1):
        start, end = int(boundaries[k]), int(boundaries[k + 1])
        side = int(s[start])
        if side == 0:
            equity_close[start:end] = account_equity
            continue

        trade_no += 1
        entry_ts = idx[start]
        entry_price = float(op[start])
        entry_account = float(account_equity)
        initial_margin = entry_account * margin_fraction
        entry_fee_frac = notional_fraction * cost

        # Funding is expressed as a return on account-at-entry. At the funding timestamp
        # we use the bar OPEN as the price proxy because the execution convention is OPEN.
        fund_frac = np.zeros(end - start, dtype=np.float64)
        if include_funding:
            ev = fe[start:end]
            if ev.any():
                fund_frac[ev] = -side * notional_fraction * (op[start:end][ev] / entry_price) * fr[start:end][ev]
        cum_fund = np.cumsum(fund_frac)

        rel_close = (1.0 - entry_fee_frac
                     + side * notional_fraction * (cl[start:end] / entry_price - 1.0)
                     + cum_fund)
        equity_close[start:end] = entry_account * rel_close

        if end < n:
            exit_ts = idx[end]
            exit_price = float(op[end])
            closed_by_signal = True
        else:
            exit_ts = idx[-1] + pd.Timedelta(minutes=1)
            exit_price = float(cl[-1])
            closed_by_signal = False

        exit_fee_frac = notional_fraction * (exit_price / entry_price) * cost
        price_return = side * notional_fraction * (exit_price / entry_price - 1.0)
        funding_return = float(cum_fund[-1]) if len(cum_fund) else 0.0
        net_trade_return = float(price_return + funding_return - entry_fee_frac - exit_fee_frac)
        account_after = entry_account * (1.0 + net_trade_return)

        # If dataset ends while a trade is open, include the estimated exit fee at last close.
        if end >= n:
            equity_close[-1] = account_after

        if record_trades:
            adverse_price = lo[start:end] if side > 0 else hi[start:end]
            favorable_price = hi[start:end] if side > 0 else lo[start:end]
            price_adverse = (adverse_price / entry_price - 1.0) if side > 0 else (1.0 - adverse_price / entry_price)
            price_favorable = (favorable_price / entry_price - 1.0) if side > 0 else (1.0 - favorable_price / entry_price)
            mae_loc = int(np.nanargmin(price_adverse))
            price_mae = float(price_adverse[mae_loc])
            price_mfe = float(np.nanmax(price_favorable))
            mae_time = idx[start + mae_loc]

            # Conservative intrabar equity proxy includes an estimated closing fee at the
            # adverse High/Low price. Funding accrued through each minute is included.
            est_close_fee = notional_fraction * (adverse_price / entry_price) * cost
            pnl_worst = side * notional_fraction * (adverse_price / entry_price - 1.0)
            account_rel_worst = 1.0 - entry_fee_frac + cum_fund + pnl_worst - est_close_fee
            margin_rel_of_account = margin_fraction - entry_fee_frac + cum_fund + pnl_worst - est_close_fee
            margin_remaining = margin_rel_of_account / margin_fraction
            account_mae = float(np.nanmin(account_rel_worst - 1.0))
            margin_mae = float(np.nanmin(margin_remaining - 1.0))
            min_margin_remaining = float(np.nanmin(margin_remaining))

            # Close-to-close holding drawdown. Intrabar MAE is reported separately above.
            rel_with_base = np.r_[1.0, rel_close]
            peak = np.maximum.accumulate(rel_with_base)
            holding_dd = float(np.nanmin(rel_with_base / peak - 1.0))

            one_min_adverse = ((lo[start:end] / op[start:end] - 1.0) if side > 0
                               else (1.0 - hi[start:end] / op[start:end]))
            worst_1m = float(np.nanmin(one_min_adverse))
            c = cl[start:end]
            def horizon_adverse(h):
                if len(c) <= h:
                    return np.nan
                rr = side * (c[h:] / c[:-h] - 1.0)
                return float(np.nanmin(rr))
            worst_5m = horizon_adverse(5)
            worst_15m = horizon_adverse(15)

            margin_loss = -margin_mae
            if min_margin_remaining <= 0.0 or margin_loss >= 0.90:
                risk = "DANGER"
            elif margin_loss >= 0.70:
                risk = "WARNING"
            else:
                risk = "OK"

            segment = "train" if entry_ts < train_end else "validation"
            crosses = bool(entry_ts < train_end <= exit_ts)
            trade = {
                "alpha_id": "",  # filled by caller
                "episode_id": f"TRADE_{trade_no:05d}",
                "segment": segment,
                "crosses_train_validation": crosses,
                "side": "LONG" if side > 0 else "SHORT",
                "entry_time_utc": entry_ts.isoformat(),
                "exit_time_utc": exit_ts.isoformat(),
                "entry_time_ms": int(entry_ts.timestamp() * 1000),
                "exit_time_ms": int(exit_ts.timestamp() * 1000),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "holding_minutes": int(max(1, round((exit_ts - entry_ts).total_seconds() / 60.0))),
                "margin_fraction": margin_fraction,
                "leverage": leverage,
                "entry_notional_fraction_of_account": notional_fraction,
                "gross_price_return_on_account": float(price_return),
                "funding_return_on_account": funding_return,
                "entry_fee_return_on_account": float(entry_fee_frac),
                "exit_fee_return_on_account": float(exit_fee_frac),
                "net_return_on_account": net_trade_return,
                "price_mae": price_mae,
                "price_mfe": price_mfe,
                "margin_equity_mae": margin_mae,
                "account_equity_mae": account_mae,
                "min_margin_remaining_fraction": min_margin_remaining,
                "proxy_margin_breached": bool(min_margin_remaining <= 0.0),
                "price_buffer_to_10pct_adverse_move": float(0.10 - abs(min(price_mae, 0.0))),
                "mae_time_utc": mae_time.isoformat(),
                "mae_time_ms": int(mae_time.timestamp() * 1000),
                "holding_max_drawdown_close": holding_dd,
                "worst_1m_adverse_move": worst_1m,
                "worst_5m_close_to_close_move": worst_5m,
                "worst_15m_close_to_close_move": worst_15m,
                "risk_10x": risk,
                "closed_by_signal": closed_by_signal,
            }
            trades.append(trade)
            events.append({
                "alpha_id": "", "timestamp_utc": entry_ts.isoformat(),
                "timestamp_ms": int(entry_ts.timestamp() * 1000), "segment": segment,
                "execution_price": entry_price, "action": "OPEN_LONG" if side > 0 else "OPEN_SHORT",
                "new_state": side, "margin_fraction": margin_fraction, "leverage": leverage,
            })
            if closed_by_signal:
                events.append({
                    "alpha_id": "", "timestamp_utc": exit_ts.isoformat(),
                    "timestamp_ms": int(exit_ts.timestamp() * 1000),
                    "segment": "train" if exit_ts < train_end else "validation",
                    "execution_price": exit_price, "action": "CLOSE_LONG" if side > 0 else "CLOSE_SHORT",
                    "new_state": 0, "margin_fraction": margin_fraction, "leverage": leverage,
                })

        account_equity = float(account_after)

    # Fill any leading/trailing holes defensively.
    eq = pd.Series(equity_close, index=idx).ffill().fillna(1.0)
    returns = eq.pct_change().fillna(eq.iloc[0] / 1.0 - 1.0)
    return {"returns": returns, "equity": eq, "state": pd.Series(s, index=idx, dtype="float32"),
            "trades": trades, "events": events}


def _trade_risk_aggregate(trades: list[dict], segment: str, side: str | None = None) -> dict:
    x = [t for t in trades if t["segment"] == segment and not t.get("crosses_train_validation")]
    if side:
        x = [t for t in x if t["side"] == side]
    if not x:
        return {"trades": 0, "price_mae_abs_p95": np.nan, "price_mae_abs_p99": np.nan,
                "worst_price_mae": np.nan, "worst_margin_equity_mae": np.nan,
                "worst_account_equity_mae": np.nan, "min_margin_remaining_fraction": np.nan,
                "danger_trades": 0, "warning_trades": 0, "proxy_margin_breaches": 0}
    adverse = np.array([abs(min(float(t["price_mae"]), 0.0)) for t in x], float)
    return {
        "trades": len(x),
        "price_mae_abs_p95": float(np.quantile(adverse, .95)),
        "price_mae_abs_p99": float(np.quantile(adverse, .99)),
        "worst_price_mae": float(min(float(t["price_mae"]) for t in x)),
        "worst_margin_equity_mae": float(min(float(t["margin_equity_mae"]) for t in x)),
        "worst_account_equity_mae": float(min(float(t["account_equity_mae"]) for t in x)),
        "min_margin_remaining_fraction": float(min(float(t["min_margin_remaining_fraction"]) for t in x)),
        "danger_trades": int(sum(t["risk_10x"] == "DANGER" for t in x)),
        "warning_trades": int(sum(t["risk_10x"] == "WARNING" for t in x)),
        "proxy_margin_breaches": int(sum(bool(t["proxy_margin_breached"]) for t in x)),
    }


def _beijing_month_bounds(index: pd.DatetimeIndex):
    tz = "Asia/Shanghai"
    first = index.min().tz_convert(tz)
    last = index.max().tz_convert(tz)
    cur = pd.Timestamp(year=first.year, month=first.month, day=1, tz=tz)
    end = pd.Timestamp(year=last.year, month=last.month, day=1, tz=tz) + pd.offsets.MonthBegin(1)
    while cur < end:
        nxt = cur + pd.offsets.MonthBegin(1)
        yield cur.strftime("%Y-%m"), cur.tz_convert("UTC"), nxt.tz_convert("UTC")
        cur = nxt


def _write_market_replay(df: pd.DataFrame, replay_dir: Path, overview_minutes: int) -> list[str]:
    """Write Beijing-natural-month replay data.

    Month overview is 15m JSON. Detailed 1m data uses a compact gzip stream:
    16-byte header (<qii: start_utc_ms, row_count, reserved), followed by
    int32 OHLC deltas in cents relative to the previous close (16 bytes/row).
    Because BTC futures 1m has no missing minutes in the locked visible dataset,
    timestamps are reconstructed as start + i*60s. This materially reduces Git push size.
    """
    import shutil, gzip, struct
    overview_dir = replay_dir / f"market_{overview_minutes}m"
    detail_dir = replay_dir / "market_1m"
    for p in (overview_dir, detail_dir):
        if p.exists(): shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)
    bars = df[["open", "high", "low", "close"]].astype(float).resample(f"{overview_minutes}min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()
    months=[]
    for month, utc_start, utc_end in _beijing_month_bounds(df.index):
        months.append(month)
        part=bars[(bars.index>=utc_start)&(bars.index<utc_end)]
        rows=[[int(ts.timestamp()*1000),round(float(r.open),2),round(float(r.high),2),round(float(r.low),2),round(float(r.close),2)] for ts,r in part.iterrows()]
        (overview_dir/f"{month}.json").write_text(json.dumps({"bar_minutes":overview_minutes,"rows":rows},separators=(",",":"),ensure_ascii=False),encoding="utf-8")

        one=df[(df.index>=utc_start)&(df.index<utc_end)]
        if one.empty:
            continue
        ns=one.index.asi8
        if len(ns)>1 and not np.all(np.diff(ns)==60_000_000_000):
            raise ValueError(f"1m replay binary requires continuous futures minutes: {month}")
        cents=np.rint(one[["open","high","low","close"]].to_numpy(dtype=float)*100.0).astype(np.int64)
        prev=np.empty(len(one),dtype=np.int64)
        prev[0]=0
        if len(one)>1: prev[1:]=cents[:-1,3]
        delta=(cents-prev[:,None])
        if delta.min()<np.iinfo(np.int32).min or delta.max()>np.iinfo(np.int32).max:
            raise OverflowError("1m replay OHLC delta exceeded int32 range")
        payload=struct.pack("<qii",int(one.index[0].timestamp()*1000),len(one),0)+delta.astype("<i4").tobytes(order="C")
        (detail_dir/f"{month}.bin.gz").write_bytes(gzip.compress(payload,compresslevel=6))
    return months


def _write_signal_replay(alpha_id: str, trace: pd.DataFrame, replay_dir: Path) -> None:
    """Gzip 20-byte records: UTC-ms float64, z float32, smoothed float32, state float32."""
    import gzip
    out=replay_dir/"signals"/alpha_id
    out.mkdir(parents=True,exist_ok=True)
    dtype=np.dtype([("t","<f8"),("z","<f4"),("s","<f4"),("p","<f4")])
    if trace.empty:return
    for month,utc_start,utc_end in _beijing_month_bounds(trace.index):
        part=trace[(trace.index>=utc_start)&(trace.index<utc_end)]
        if part.empty:continue
        arr=np.empty(len(part),dtype=dtype)
        arr["t"]=part.index.asi8/1_000_000.0
        arr["z"]=part["zscore"].to_numpy(np.float32)
        arr["s"]=part["smoothed_target"].to_numpy(np.float32)
        arr["p"]=part["fixed_state"].to_numpy(np.float32)
        (out/f"{month}.bin.gz").write_bytes(gzip.compress(arr.tobytes(order="C"),compresslevel=6))

def run_phase2(config_path: Path, data_path: Path, output_root: Path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not config.get("test_locked", False):
        raise ValueError("Phase 2 requires test_locked=true.")

    df = load_visible_data(data_path, config)
    train_end = pd.Timestamp(config["train_end"])
    validation_end = pd.Timestamp(config["validation_end"])
    train = pd.Series(df.index < train_end, index=df.index)
    validation = pd.Series((df.index >= train_end) & (df.index < validation_end), index=df.index)
    close = df["close"].astype(float)

    signal_cfg=config["signal"];eval_cfg=config["evaluation"];cost_cfg=config["costs"]
    base_cost=float(cost_cfg["base_cost_bps_one_way"])
    scenarios=sorted(set(float(x) for x in cost_cfg["sensitivity_bps_one_way"]+[base_cost]))
    diag_cfg=config.get("diagnostics",{})
    margin_fraction=float(diag_cfg.get("margin_fraction",0.10))
    leverage=float(diag_cfg.get("leverage",10))
    if abs(margin_fraction-.10)>1e-12 or abs(leverage-10)>1e-12:
        raise ValueError("Diagnostics are fixed to 10% isolated margin and 10x leverage.")
    overview_minutes=int(diag_cfg.get("replay_overview_bar_minutes",15))
    asymmetry_ratio=float(diag_cfg.get("direction_asymmetry_ratio",1.75))
    beta_windows=[int(x) for x in diag_cfg.get("rolling_beta_windows_minutes",[60,240,1440])]

    result_dir=output_root/"results"/"phase2_low_turnover";result_dir.mkdir(parents=True,exist_ok=True)
    replay_dir=result_dir/"replay"
    if replay_dir.exists():
        import shutil;shutil.rmtree(replay_dir)
    (replay_dir/"factors").mkdir(parents=True,exist_ok=True)

    rows=[];cost_rows=[];yearly_rows=[];diagnostic_rows=[];trade_rows=[];event_rows=[];beta_profile=[]
    for number,feature_spec in enumerate(iter_feature_specs(df),1):
        print(f"[{number:02d}] {feature_spec.alpha_id}",flush=True)
        feature=feature_spec.feature
        position,trace=build_position(
            feature=feature,
            normalization_lookback=int(signal_cfg["normalization_lookback_minutes"]),
            clip_z=float(signal_cfg["clip_z"]),
            rebalance_minutes=feature_spec.rebalance_minutes,
            smoothing_halflife=feature_spec.smoothing_halflife_minutes,
            no_trade_band=feature_spec.no_trade_band,
            position_step=float(signal_cfg["position_step"]),
            position_cap=float(signal_cfg["position_cap"]),
            return_trace=True,
        )

        # Original official Phase2 metrics remain untouched for historical comparability.
        gross,turnover,funding_pnl=_strategy_components(df,position,bool(cost_cfg.get("include_actual_funding",True)))
        base_returns=gross-turnover*base_cost/10000.0
        train_metrics=daily_metrics(base_returns[train],position[train],gross[train])
        validation_metrics=daily_metrics(base_returns[validation],position[validation],gross[validation])
        train_ic=predictive_metrics(feature,close,train,list(eval_cfg["forward_return_horizons_minutes"]),int(eval_cfg["ic_sample_every_minutes"]))
        validation_ic=predictive_metrics(feature,close,validation,list(eval_cfg["forward_return_horizons_minutes"]),int(eval_cfg["ic_sample_every_minutes"]))

        factor_yearly_rows=[];positive_year_fraction={}
        for segment_name,segment_mask in (("train",train),("validation",validation)):
            segment_returns=base_returns[segment_mask];segment_position=position[segment_mask];segment_gross=gross[segment_mask]
            segment_year_rows=[]
            for year,year_returns in segment_returns.groupby(segment_returns.index.year):
                ix=year_returns.index;values=daily_metrics(year_returns,segment_position.loc[ix],segment_gross.loc[ix])
                yr={"alpha_id":feature_spec.alpha_id,"segment":segment_name,"year":int(year),**values}
                factor_yearly_rows.append(yr);segment_year_rows.append(yr)
            positive_year_fraction[segment_name]=(sum(float(x.get("net_return",0.0))>0.0 for x in segment_year_rows)/len(segment_year_rows) if segment_year_rows else 0.0)
        yearly_rows.extend(factor_yearly_rows)
        direction_consistent=np.sign(train_metrics.get("net_sharpe_daily",0.0))==np.sign(validation_metrics.get("net_sharpe_daily",0.0))
        candidate=(validation_metrics.get("net_sharpe_daily",-np.inf)>=float(eval_cfg["validation_net_sharpe_min"])
            and train_metrics.get("max_drawdown",-np.inf)>=float(eval_cfg["train_max_drawdown_floor"])
            and validation_metrics.get("max_drawdown",-np.inf)>=float(eval_cfg["validation_max_drawdown_floor"])
            and positive_year_fraction["train"]>=float(eval_cfg["min_positive_train_year_fraction"])
            and positive_year_fraction["validation"]>=float(eval_cfg["min_positive_validation_year_fraction"])
            and (not eval_cfg.get("require_positive_train_sharpe",True) or train_metrics.get("net_sharpe_daily",-np.inf)>0.0)
            and (not eval_cfg.get("require_positive_validation_return",True) or validation_metrics.get("net_return",-np.inf)>0.0)
            and direction_consistent)
        row={"alpha_id":feature_spec.alpha_id,"family":feature_spec.family,"hypothesis":feature_spec.hypothesis,
             "rebalance_minutes":feature_spec.rebalance_minutes,"smoothing_halflife_minutes":feature_spec.smoothing_halflife_minutes,
             "no_trade_band":feature_spec.no_trade_band,"base_cost_bps_one_way":base_cost,
             **{f"train_{k}":v for k,v in train_metrics.items()},**{f"train_{k}":v for k,v in train_ic.items()},
             **{f"val_{k}":v for k,v in validation_metrics.items()},**{f"val_{k}":v for k,v in validation_ic.items()},
             "train_positive_year_fraction":positive_year_fraction["train"],"val_positive_year_fraction":positive_year_fraction["validation"],
             "direction_consistent":bool(direction_consistent),"phase2_candidate":bool(candidate)}

        # New fixed single-alpha execution model. Existing alpha definition is unchanged;
        # only the execution/risk/diagnostic layer is different.
        state=_fixed_state(position)
        sim=_fixed_single_alpha_simulation(df,state,base_cost,bool(cost_cfg.get("include_actual_funding",True)),margin_fraction,leverage,train_end,True)
        for t in sim["trades"]:t["alpha_id"]=feature_spec.alpha_id
        for e in sim["events"]:e["alpha_id"]=feature_spec.alpha_id
        trade_rows.extend(sim["trades"]);event_rows.extend(sim["events"])

        long_state=state.where(state>0,0.0);short_state=state.where(state<0,0.0)
        long_sim=_fixed_single_alpha_simulation(df,long_state,base_cost,bool(cost_cfg.get("include_actual_funding",True)),margin_fraction,leverage,train_end,False)
        short_sim=_fixed_single_alpha_simulation(df,short_state,base_cost,bool(cost_cfg.get("include_actual_funding",True)),margin_fraction,leverage,train_end,False)

        fixed_train=_simple_strategy_metrics(sim["returns"][train],state[train]);fixed_val=_simple_strategy_metrics(sim["returns"][validation],state[validation])
        long_train=_simple_strategy_metrics(long_sim["returns"][train],long_state[train]);long_val=_simple_strategy_metrics(long_sim["returns"][validation],long_state[validation])
        short_train=_simple_strategy_metrics(short_sim["returns"][train],short_state[train]);short_val=_simple_strategy_metrics(short_sim["returns"][validation],short_state[validation])
        direction_type,dominant_side=_direction_type_from_train(long_train.get("net_sharpe_daily",np.nan),short_train.get("net_sharpe_daily",np.nan),asymmetry_ratio)

        beta_train=_beta_metrics(sim["returns"],df,train);beta_val=_beta_metrics(sim["returns"],df,validation)
        long_beta_train=_beta_metrics(long_sim["returns"],df,train);long_beta_val=_beta_metrics(long_sim["returns"],df,validation)
        short_beta_train=_beta_metrics(short_sim["returns"],df,train);short_beta_val=_beta_metrics(short_sim["returns"],df,validation)
        regime_train=_regime_beta_metrics(sim["returns"],df,train);regime_val=_regime_beta_metrics(sim["returns"],df,validation)
        beta_profile.extend(_beta_profile_rows(feature_spec.alpha_id,sim["returns"],df,train,validation,beta_windows))

        train_risk=_trade_risk_aggregate(sim["trades"],"train")
        val_risk=_trade_risk_aggregate(sim["trades"],"validation")
        train_long_risk=_trade_risk_aggregate(sim["trades"],"train","LONG")
        train_short_risk=_trade_risk_aggregate(sim["trades"],"train","SHORT")
        val_long_risk=_trade_risk_aggregate(sim["trades"],"validation","LONG")
        val_short_risk=_trade_risk_aggregate(sim["trades"],"validation","SHORT")

        row.update({
            "direction_type_train":direction_type,"dominant_side_train":dominant_side,
            **{f"fixed_train_{k}":v for k,v in fixed_train.items()},**{f"fixed_val_{k}":v for k,v in fixed_val.items()},
            "fixed_train_long_sharpe":long_train.get("net_sharpe_daily",np.nan),"fixed_train_short_sharpe":short_train.get("net_sharpe_daily",np.nan),
            "fixed_val_long_sharpe":long_val.get("net_sharpe_daily",np.nan),"fixed_val_short_sharpe":short_val.get("net_sharpe_daily",np.nan),
            "fixed_train_beta_btc_daily":beta_train.get("beta_btc_daily",np.nan),"fixed_train_beta_eth_daily":beta_train.get("beta_eth_daily",np.nan),
            "fixed_train_residual_sharpe_daily":beta_train.get("residual_sharpe_daily",np.nan),
            "fixed_val_beta_btc_daily":beta_val.get("beta_btc_daily",np.nan),"fixed_val_beta_eth_daily":beta_val.get("beta_eth_daily",np.nan),
            "fixed_val_residual_sharpe_daily":beta_val.get("residual_sharpe_daily",np.nan),
            "fixed_val_worst_price_mae":val_risk.get("worst_price_mae",np.nan),
            "fixed_val_worst_margin_equity_mae":val_risk.get("worst_margin_equity_mae",np.nan),
            "fixed_val_worst_account_equity_mae":val_risk.get("worst_account_equity_mae",np.nan),
            "fixed_val_min_margin_remaining_fraction":val_risk.get("min_margin_remaining_fraction",np.nan),
            "fixed_val_10x_danger_trades":val_risk.get("danger_trades",0),"fixed_val_proxy_margin_breaches":val_risk.get("proxy_margin_breaches",0),
        })
        diagnostic={"alpha_id":feature_spec.alpha_id,"family":feature_spec.family,"direction_type_train":direction_type,"dominant_side_train":dominant_side,
            "execution_model":"ONE_ALPHA_10PCT_ISOLATED_MARGIN_10X_FIXED_DIRECTION","margin_fraction":margin_fraction,"leverage":leverage,
            "entry_notional_fraction_of_account":margin_fraction*leverage,"execution_price":"NEXT_BAR_OPEN_AFTER_T_MINUS_1_INFORMATION",
            "no_pyramiding":True,"liquidation_model":"10X_MARGIN_STRESS_PROXY_NOT_EXACT_BINANCE_LIQUIDATION",
            **{f"combined_train_{k}":v for k,v in beta_train.items()},**{f"combined_val_{k}":v for k,v in beta_val.items()},
            **{f"combined_train_regime_{k}":v for k,v in regime_train.items()},**{f"combined_val_regime_{k}":v for k,v in regime_val.items()},
            **{f"long_train_{k}":v for k,v in long_train.items()},**{f"long_val_{k}":v for k,v in long_val.items()},
            **{f"short_train_{k}":v for k,v in short_train.items()},**{f"short_val_{k}":v for k,v in short_val.items()},
            **{f"long_train_beta_{k}":v for k,v in long_beta_train.items()},**{f"long_val_beta_{k}":v for k,v in long_beta_val.items()},
            **{f"short_train_beta_{k}":v for k,v in short_beta_train.items()},**{f"short_val_beta_{k}":v for k,v in short_beta_val.items()},
            **{f"train_risk_{k}":v for k,v in train_risk.items()},**{f"val_risk_{k}":v for k,v in val_risk.items()},
            **{f"train_long_risk_{k}":v for k,v in train_long_risk.items()},**{f"train_short_risk_{k}":v for k,v in train_short_risk.items()},
            **{f"val_long_risk_{k}":v for k,v in val_long_risk.items()},**{f"val_short_risk_{k}":v for k,v in val_short_risk.items()}}
        diagnostic_rows.append(diagnostic)

        factor_replay={"schema_version":2,"alpha_id":feature_spec.alpha_id,"family":feature_spec.family,"hypothesis":feature_spec.hypothesis,
            "direction_type_train":direction_type,"dominant_side_train":dominant_side,
            "trade_model":{"single_alpha":True,"margin_fraction":margin_fraction,"leverage":leverage,"isolated_margin":True,"notional_fraction":margin_fraction*leverage,
                           "execution":"signal formed with t-1 information; execute at t open","no_pyramiding":True},
            "liquidation_model":"10x margin stress proxy; exact Binance liquidation requires historical Mark Price and maintenance-margin tiers",
            "beta":{"train_btc":_json_value(beta_train.get("beta_btc_daily")),"train_eth":_json_value(beta_train.get("beta_eth_daily")),
                    "train_residual_sharpe":_json_value(beta_train.get("residual_sharpe_daily")),"validation_btc":_json_value(beta_val.get("beta_btc_daily")),
                    "validation_eth":_json_value(beta_val.get("beta_eth_daily")),"validation_residual_sharpe":_json_value(beta_val.get("residual_sharpe_daily"))},
            "events":sim["events"],"episodes":sim["trades"]}
        (replay_dir/"factors"/f"{feature_spec.alpha_id}.json").write_text(json.dumps(factor_replay,separators=(",",":"),ensure_ascii=False,default=_json_value),encoding="utf-8")
        _write_signal_replay(feature_spec.alpha_id,trace,replay_dir)
        rows.append(row)

        for cost_bps in scenarios:
            scenario_return=gross-turnover*cost_bps/10000.0
            for segment_name,segment_mask in (("train",train),("validation",validation)):
                values=daily_metrics(scenario_return[segment_mask],position[segment_mask],gross[segment_mask])
                cost_rows.append({"alpha_id":feature_spec.alpha_id,"segment":segment_name,"cost_bps_one_way":cost_bps,**values})
        del feature,position,trace,gross,turnover,funding_pnl,base_returns,state,sim,long_sim,short_sim
        gc.collect()

    leaderboard=pd.DataFrame(rows).sort_values(["phase2_candidate","val_net_sharpe_daily"],ascending=[False,False])
    cost_sensitivity=pd.DataFrame(cost_rows);yearly=pd.DataFrame(yearly_rows);factor_diagnostics=pd.DataFrame(diagnostic_rows)
    trade_ledger=pd.DataFrame(trade_rows);trade_events=pd.DataFrame(event_rows);beta_profile_df=pd.DataFrame(beta_profile)
    leaderboard.to_csv(result_dir/"alpha_leaderboard.csv",index=False);cost_sensitivity.to_csv(result_dir/"cost_sensitivity.csv",index=False)
    yearly.to_csv(result_dir/"yearly_metrics.csv",index=False);factor_diagnostics.to_csv(result_dir/"factor_diagnostics.csv",index=False)
    trade_ledger.to_csv(result_dir/"trade_ledger.csv",index=False);trade_events.to_csv(result_dir/"trade_events.csv",index=False)
    beta_profile_df.to_csv(result_dir/"beta_profile.csv",index=False)

    replay_months=_write_market_replay(df,replay_dir,overview_minutes)
    replay_index={"schema_version":2,"display_timezone":"Asia/Shanghai","overview_bar_minutes":overview_minutes,"detail_bar_minutes":1,
        "market_1m_format":"gzip_delta_int32_cents_v1","market_1m_record_bytes_uncompressed":16,"signal_format":"gzip_float_v1","signal_binary_record_bytes_uncompressed":20,"months":replay_months,"test_locked":True,
        "visible_start_utc":str(df.index.min()),"visible_end_utc":str(df.index.max()),
        "alphas":[{"alpha_id":r["alpha_id"],"family":r["family"],"direction_type_train":r.get("direction_type_train"),"dominant_side_train":r.get("dominant_side_train")} for r in rows]}
    (result_dir/"replay_index.json").write_text(json.dumps(replay_index,indent=2,ensure_ascii=False,default=_json_value),encoding="utf-8")

    summary={"schema_version":3,"status":"PHASE2_EXISTING_FACTOR_ANALYTICS_TRAIN_VALIDATION_ONLY","test_locked":True,
        "test_start":str(validation_end),"visible_start":str(df.index.min()),"visible_end":str(df.index.max()),"rows_visible":int(len(df)),
        "alphas_researched":int(len(leaderboard)),"phase2_candidates":int(leaderboard["phase2_candidate"].sum()),"base_cost_bps_one_way":base_cost,
        "cost_scenarios_bps_one_way":scenarios,"funding_included":bool(cost_cfg.get("include_actual_funding",True)),"existing_factor_diagnostics_only":True,
        "new_alpha_logic_added":False,"single_alpha_trade_model":{"margin_fraction":margin_fraction,"leverage":leverage,"isolated_margin":True,
        "entry_notional_fraction_of_account":margin_fraction*leverage,"execution_price":"bar_open","no_pyramiding":True},
        "liquidation_model":"10X_MARGIN_STRESS_PROXY_NOT_EXACT_BINANCE_LIQUIDATION","display_timezone":"Asia/Shanghai",
        "replay_overview_bar_minutes":overview_minutes,"replay_detail_bar_minutes":1,
        "output_files":["results/phase2_low_turnover/alpha_leaderboard.csv","results/phase2_low_turnover/cost_sensitivity.csv",
        "results/phase2_low_turnover/yearly_metrics.csv","results/phase2_low_turnover/factor_diagnostics.csv","results/phase2_low_turnover/beta_profile.csv",
        "results/phase2_low_turnover/trade_ledger.csv","results/phase2_low_turnover/trade_events.csv","results/phase2_low_turnover/replay_index.json",
        "results/phase2_low_turnover/replay/"]}
    (result_dir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=_json_value),encoding="utf-8")
    return leaderboard,summary
