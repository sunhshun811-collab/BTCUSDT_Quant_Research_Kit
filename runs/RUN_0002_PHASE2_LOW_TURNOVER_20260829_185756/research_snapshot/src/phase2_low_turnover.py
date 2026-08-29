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
) -> pd.Series:
    normalized = rolling_zscore(feature.astype(float), normalization_lookback)
    desired = (normalized.clip(-clip_z, clip_z) / clip_z).clip(-position_cap, position_cap)

    # A position used for return t may only use the feature observed through t-1.
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
    return sparse.reindex(feature.index, method="ffill").fillna(0.0).astype("float32")


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
    daily = returns.dropna().resample("1D").sum().dropna()
    if len(daily) < 2:
        return np.nan
    sd = daily.std(ddof=1)
    return float(daily.mean() / sd * math.sqrt(365.25)) if sd > 0 else 0.0


def _beta_metrics(
    strategy_returns: pd.Series,
    df: pd.DataFrame,
    mask: pd.Series,
) -> dict:
    """Daily OLS beta diagnostics plus 1m correlations.

    These are exposure diagnostics, not alpha-selection rules.
    """
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

    y = s.resample("1D").sum().rename("strategy")
    cols = [y]
    names = []
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
    out["residual_sharpe_daily"] = (
        float(resid_s.mean() / sd * math.sqrt(365.25)) if sd > 0 else 0.0
    )
    offset = 1
    if "btc" in names:
        out["beta_btc_daily"] = float(coef[offset + names.index("btc")])
    if "eth" in names:
        out["beta_eth_daily"] = float(coef[offset + names.index("eth")])
    return out


def _sleeve_position(position: pd.Series, side: str) -> pd.Series:
    if side == "long":
        return position.clip(lower=0.0).astype("float32")
    if side == "short":
        return position.clip(upper=0.0).astype("float32")
    return position.astype("float32")


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


def _event_action(prev_pos: float, new_pos: float) -> str:
    eps = 1e-9
    if abs(prev_pos) <= eps and new_pos > eps:
        return "OPEN_LONG"
    if abs(prev_pos) <= eps and new_pos < -eps:
        return "OPEN_SHORT"
    if prev_pos > eps and abs(new_pos) <= eps:
        return "CLOSE_LONG"
    if prev_pos < -eps and abs(new_pos) <= eps:
        return "CLOSE_SHORT"
    if prev_pos > eps and new_pos < -eps:
        return "FLIP_TO_SHORT"
    if prev_pos < -eps and new_pos > eps:
        return "FLIP_TO_LONG"
    if prev_pos >= 0 and new_pos >= 0:
        return "ADD_LONG" if new_pos > prev_pos else "REDUCE_LONG"
    if prev_pos <= 0 and new_pos <= 0:
        return "ADD_SHORT" if abs(new_pos) > abs(prev_pos) else "REDUCE_SHORT"
    return "POSITION_CHANGE"


def _position_events(
    alpha_id: str,
    position: pd.Series,
    close: pd.Series,
    train_end: pd.Timestamp,
) -> list[dict]:
    prev = position.shift(1).fillna(0.0)
    changed = (position - prev).abs() > 1e-9
    rows = []
    for ts in position.index[changed]:
        p0 = float(prev.loc[ts])
        p1 = float(position.loc[ts])
        rows.append({
            "alpha_id": alpha_id,
            "timestamp": ts.isoformat(),
            "timestamp_ms": int(ts.timestamp() * 1000),
            "segment": "train" if ts < train_end else "validation",
            "price": float(close.loc[ts]),
            "prev_position": p0,
            "new_position": p1,
            "delta_position": p1 - p0,
            "action": _event_action(p0, p1),
        })
    return rows


def _holding_episodes(
    alpha_id: str,
    segment_name: str,
    df_seg: pd.DataFrame,
    position: pd.Series,
    gross: pd.Series,
    net: pd.Series,
    funding_pnl: pd.Series,
    turnover: pd.Series,
    base_cost_bps: float,
    warning_move: float,
    danger_move: float,
) -> list[dict]:
    if df_seg.empty:
        return []
    pos = position.reindex(df_seg.index).fillna(0.0).astype(float)
    signs = np.sign(pos.to_numpy())
    idx = df_seg.index
    episodes = []
    i = 0
    episode_id = 0
    n = len(idx)
    while i < n:
        if signs[i] == 0:
            i += 1
            continue
        sign = signs[i]
        j = i + 1
        while j < n and signs[j] == sign:
            j += 1

        episode_id += 1
        sl = slice(i, j)
        ts0, ts1 = idx[i], idx[j - 1]
        frame = df_seg.iloc[sl]
        ep_pos = pos.iloc[sl]
        ep_gross = gross.reindex(idx).iloc[sl].fillna(0.0)
        ep_net = net.reindex(idx).iloc[sl].fillna(0.0)
        ep_funding = funding_pnl.reindex(idx).iloc[sl].fillna(0.0)
        ep_turn = turnover.reindex(idx).iloc[sl].fillna(0.0)

        entry = float(frame["close"].iloc[0])
        exit_price = float(frame["close"].iloc[-1])
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)

        if sign > 0:
            side = "LONG"
            mae = float(low.min() / entry - 1.0)
            mfe = float(high.max() / entry - 1.0)
            running_best = high.cummax()
            holding_dd = float((low / running_best - 1.0).min())
        else:
            side = "SHORT"
            mae = float(-(high.max() / entry - 1.0))
            mfe = float(1.0 - low.min() / entry)
            running_best = low.cummin()
            holding_dd = float((-(high / running_best - 1.0)).min())

        adverse_abs = abs(min(mae, 0.0))
        if adverse_abs >= danger_move:
            risk = "DANGER"
        elif adverse_abs >= warning_move:
            risk = "WARNING"
        else:
            risk = "OK"

        gross_return = float((1.0 + ep_gross).prod() - 1.0)
        net_return = float((1.0 + ep_net).prod() - 1.0)
        funding_return = float(ep_funding.sum())
        trading_cost = float(ep_turn.sum() * base_cost_bps / 10000.0)

        episodes.append({
            "alpha_id": alpha_id,
            "episode_id": f"{segment_name.upper()}_{episode_id:05d}",
            "segment": segment_name,
            "side": side,
            "entry_time": ts0.isoformat(),
            "exit_time": ts1.isoformat(),
            "entry_time_ms": int(ts0.timestamp() * 1000),
            "exit_time_ms": int(ts1.timestamp() * 1000),
            "entry_price": entry,
            "exit_price": exit_price,
            "holding_minutes": int((ts1 - ts0).total_seconds() // 60) + 1,
            "mean_abs_position": float(ep_pos.abs().mean()),
            "gross_return": gross_return,
            "net_return": net_return,
            "funding_return": funding_return,
            "trading_cost_return": trading_cost,
            "mae": mae,
            "mfe": mfe,
            "holding_max_drawdown": holding_dd,
            "mae_10x_equity_proxy": float(mae * 10.0),
            "buffer_to_10pct_adverse_move": float(0.10 - adverse_abs),
            "risk_10x": risk,
            "closed_by_signal": bool(j < n),
        })
        i = j
    return episodes


def _episode_aggregate(episodes: list[dict], segment: str, side: str) -> dict:
    x = [e for e in episodes if e["segment"] == segment and e["side"] == side]
    if not x:
        return {
            "episodes": 0, "mae_abs_p95": np.nan, "mae_abs_p99": np.nan,
            "worst_mae": np.nan, "worst_holding_drawdown": np.nan,
            "max_holding_minutes": np.nan, "danger_count": 0, "warning_count": 0,
        }
    adverse = np.array([abs(min(float(e["mae"]), 0.0)) for e in x], dtype=float)
    return {
        "episodes": len(x),
        "mae_abs_p95": float(np.quantile(adverse, 0.95)),
        "mae_abs_p99": float(np.quantile(adverse, 0.99)),
        "worst_mae": float(min(float(e["mae"]) for e in x)),
        "worst_holding_drawdown": float(min(float(e["holding_max_drawdown"]) for e in x)),
        "max_holding_minutes": int(max(int(e["holding_minutes"]) for e in x)),
        "danger_count": int(sum(e["risk_10x"] == "DANGER" for e in x)),
        "warning_count": int(sum(e["risk_10x"] == "WARNING" for e in x)),
    }


def _write_market_replay(df: pd.DataFrame, replay_dir: Path, bar_minutes: int) -> list[str]:
    """Write compact monthly OHLC chunks for the web replay.

    This is derived display data. It contains no factor logic and never exposes Test.
    """
    market_dir = replay_dir / f"market_{bar_minutes}m"
    if market_dir.exists():
        import shutil
        shutil.rmtree(market_dir)
    market_dir.mkdir(parents=True, exist_ok=True)

    rule = f"{max(int(bar_minutes), 1)}min"
    bars = df[["open", "high", "low", "close"]].astype(float).resample(rule).agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()
    months = []
    for month, part in bars.groupby(bars.index.strftime("%Y-%m")):
        month = str(month)
        months.append(month)
        rows = [
            [int(ts.timestamp() * 1000),
             round(float(r.open), 2), round(float(r.high), 2),
             round(float(r.low), 2), round(float(r.close), 2)]
            for ts, r in part.iterrows()
        ]
        (market_dir / f"{month}.json").write_text(
            json.dumps({"bar_minutes": int(bar_minutes), "rows": rows},
                       separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
    return months

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

    signal_cfg = config["signal"]
    eval_cfg = config["evaluation"]
    cost_cfg = config["costs"]
    base_cost = float(cost_cfg["base_cost_bps_one_way"])
    scenarios = sorted(set(float(x) for x in cost_cfg["sensitivity_bps_one_way"] + [base_cost]))

    diag_cfg = config.get("diagnostics", {})
    leverage = int(diag_cfg.get("leverage", 10))
    if leverage != 10:
        raise ValueError("This research profile only supports leverage=10 for risk diagnostics.")
    warning_move = float(diag_cfg.get("warning_adverse_move", 0.07))
    danger_move = float(diag_cfg.get("danger_adverse_move", 0.09))
    replay_bar_minutes = int(diag_cfg.get("replay_bar_minutes", 15))
    asymmetry_ratio = float(diag_cfg.get("direction_asymmetry_ratio", 1.75))

    result_dir = output_root / "results" / "phase2_low_turnover"
    result_dir.mkdir(parents=True, exist_ok=True)
    replay_dir = result_dir / "replay"
    if replay_dir.exists():
        import shutil
        shutil.rmtree(replay_dir)
    (replay_dir / "factors").mkdir(parents=True, exist_ok=True)

    rows, cost_rows, yearly_rows = [], [], []
    diagnostic_rows, trade_rows, event_rows = [], [], []
    specs = iter_feature_specs(df)
    for number, feature_spec in enumerate(specs, 1):
        print(f"[{number:02d}] {feature_spec.alpha_id}", flush=True)
        feature = feature_spec.feature
        position = build_position(
            feature=feature,
            normalization_lookback=int(signal_cfg["normalization_lookback_minutes"]),
            clip_z=float(signal_cfg["clip_z"]),
            rebalance_minutes=feature_spec.rebalance_minutes,
            smoothing_halflife=feature_spec.smoothing_halflife_minutes,
            no_trade_band=feature_spec.no_trade_band,
            position_step=float(signal_cfg["position_step"]),
            position_cap=float(signal_cfg["position_cap"]),
        )
        gross, turnover, funding_pnl = _strategy_components(
            df, position, bool(cost_cfg.get("include_actual_funding", True))
        )

        base_returns = gross - turnover * base_cost / 10000.0
        train_metrics = daily_metrics(base_returns[train], position[train], gross[train])
        validation_metrics = daily_metrics(base_returns[validation], position[validation], gross[validation])
        train_ic = predictive_metrics(
            feature, close, train, list(eval_cfg["forward_return_horizons_minutes"]),
            int(eval_cfg["ic_sample_every_minutes"]),
        )
        validation_ic = predictive_metrics(
            feature, close, validation, list(eval_cfg["forward_return_horizons_minutes"]),
            int(eval_cfg["ic_sample_every_minutes"]),
        )

        factor_yearly_rows = []
        positive_year_fraction = {}
        for segment_name, segment_mask in (("train", train), ("validation", validation)):
            segment_returns = base_returns[segment_mask]
            segment_position = position[segment_mask]
            segment_gross = gross[segment_mask]
            segment_year_rows = []
            for year, year_returns in segment_returns.groupby(segment_returns.index.year):
                idx = year_returns.index
                values = daily_metrics(year_returns, segment_position.loc[idx], segment_gross.loc[idx])
                year_row = {
                    "alpha_id": feature_spec.alpha_id,
                    "segment": segment_name,
                    "year": int(year),
                    **values,
                }
                factor_yearly_rows.append(year_row)
                segment_year_rows.append(year_row)
            positive_year_fraction[segment_name] = (
                sum(float(x.get("net_return", 0.0)) > 0.0 for x in segment_year_rows)
                / len(segment_year_rows) if segment_year_rows else 0.0
            )
        yearly_rows.extend(factor_yearly_rows)

        direction_consistent = (
            np.sign(train_metrics.get("net_sharpe_daily", 0.0))
            == np.sign(validation_metrics.get("net_sharpe_daily", 0.0))
        )
        candidate = (
            validation_metrics.get("net_sharpe_daily", -np.inf)
            >= float(eval_cfg["validation_net_sharpe_min"])
            and train_metrics.get("max_drawdown", -np.inf)
            >= float(eval_cfg["train_max_drawdown_floor"])
            and validation_metrics.get("max_drawdown", -np.inf)
            >= float(eval_cfg["validation_max_drawdown_floor"])
            and positive_year_fraction["train"]
            >= float(eval_cfg["min_positive_train_year_fraction"])
            and positive_year_fraction["validation"]
            >= float(eval_cfg["min_positive_validation_year_fraction"])
            and (not eval_cfg.get("require_positive_train_sharpe", True)
                 or train_metrics.get("net_sharpe_daily", -np.inf) > 0.0)
            and (not eval_cfg.get("require_positive_validation_return", True)
                 or validation_metrics.get("net_return", -np.inf) > 0.0)
            and direction_consistent
        )

        row = {
            "alpha_id": feature_spec.alpha_id,
            "family": feature_spec.family,
            "hypothesis": feature_spec.hypothesis,
            "rebalance_minutes": feature_spec.rebalance_minutes,
            "smoothing_halflife_minutes": feature_spec.smoothing_halflife_minutes,
            "no_trade_band": feature_spec.no_trade_band,
            "base_cost_bps_one_way": base_cost,
            **{f"train_{k}": v for k, v in train_metrics.items()},
            **{f"train_{k}": v for k, v in train_ic.items()},
            **{f"val_{k}": v for k, v in validation_metrics.items()},
            **{f"val_{k}": v for k, v in validation_ic.items()},
            "train_positive_year_fraction": positive_year_fraction["train"],
            "val_positive_year_fraction": positive_year_fraction["validation"],
            "direction_consistent": bool(direction_consistent),
            "phase2_candidate": bool(candidate),
        }
        # Existing-factor diagnostics only: no new Alpha logic, no validation-based direction selection.
        sleeve_data = {}
        for sleeve in ("long", "short"):
            sleeve_pos = _sleeve_position(position, sleeve)
            sleeve_gross, sleeve_turn, sleeve_funding = _strategy_components(
                df, sleeve_pos, bool(cost_cfg.get("include_actual_funding", True))
            )
            sleeve_net = sleeve_gross - sleeve_turn * base_cost / 10000.0
            sleeve_data[sleeve] = {
                "position": sleeve_pos, "gross": sleeve_gross, "turnover": sleeve_turn,
                "funding": sleeve_funding, "net": sleeve_net,
                "train_metrics": daily_metrics(sleeve_net[train], sleeve_pos[train], sleeve_gross[train]),
                "val_metrics": daily_metrics(sleeve_net[validation], sleeve_pos[validation], sleeve_gross[validation]),
                "train_beta": _beta_metrics(sleeve_net, df, train),
                "val_beta": _beta_metrics(sleeve_net, df, validation),
            }

        combined_train_beta = _beta_metrics(base_returns, df, train)
        combined_val_beta = _beta_metrics(base_returns, df, validation)
        direction_type, dominant_side = _direction_type_from_train(
            sleeve_data["long"]["train_metrics"].get("net_sharpe_daily", np.nan),
            sleeve_data["short"]["train_metrics"].get("net_sharpe_daily", np.nan),
            asymmetry_ratio,
        )

        events = _position_events(feature_spec.alpha_id, position, close, train_end)
        event_rows.extend(events)
        episodes = []
        for seg_name, seg_mask in (("train", train), ("validation", validation)):
            seg_idx = df.index[seg_mask]
            episodes.extend(_holding_episodes(
                feature_spec.alpha_id, seg_name, df.loc[seg_idx],
                position.loc[seg_idx], gross.loc[seg_idx], base_returns.loc[seg_idx],
                funding_pnl.loc[seg_idx], turnover.loc[seg_idx], base_cost,
                warning_move, danger_move,
            ))
        trade_rows.extend(episodes)

        risk = {}
        for seg_name in ("train", "validation"):
            for side_name in ("LONG", "SHORT"):
                agg = _episode_aggregate(episodes, seg_name, side_name)
                for k, v in agg.items():
                    risk[f"{seg_name}_{side_name.lower()}_{k}"] = v

        # Extend the official leaderboard with high-value diagnostics.
        row.update({
            "direction_type_train": direction_type,
            "dominant_side_train": dominant_side,
            "train_long_sharpe": sleeve_data["long"]["train_metrics"].get("net_sharpe_daily", np.nan),
            "train_short_sharpe": sleeve_data["short"]["train_metrics"].get("net_sharpe_daily", np.nan),
            "val_long_sharpe": sleeve_data["long"]["val_metrics"].get("net_sharpe_daily", np.nan),
            "val_short_sharpe": sleeve_data["short"]["val_metrics"].get("net_sharpe_daily", np.nan),
            "train_beta_btc_daily": combined_train_beta.get("beta_btc_daily", np.nan),
            "train_beta_eth_daily": combined_train_beta.get("beta_eth_daily", np.nan),
            "train_residual_sharpe_daily": combined_train_beta.get("residual_sharpe_daily", np.nan),
            "val_beta_btc_daily": combined_val_beta.get("beta_btc_daily", np.nan),
            "val_beta_eth_daily": combined_val_beta.get("beta_eth_daily", np.nan),
            "val_residual_sharpe_daily": combined_val_beta.get("residual_sharpe_daily", np.nan),
            "val_long_beta_btc_daily": sleeve_data["long"]["val_beta"].get("beta_btc_daily", np.nan),
            "val_short_beta_btc_daily": sleeve_data["short"]["val_beta"].get("beta_btc_daily", np.nan),
            "val_long_residual_sharpe_daily": sleeve_data["long"]["val_beta"].get("residual_sharpe_daily", np.nan),
            "val_short_residual_sharpe_daily": sleeve_data["short"]["val_beta"].get("residual_sharpe_daily", np.nan),
            "val_long_worst_mae": risk.get("validation_long_worst_mae", np.nan),
            "val_short_worst_mae": risk.get("validation_short_worst_mae", np.nan),
            "val_long_mae_abs_p99": risk.get("validation_long_mae_abs_p99", np.nan),
            "val_short_mae_abs_p99": risk.get("validation_short_mae_abs_p99", np.nan),
            "val_10x_danger_episodes": (
                int(risk.get("validation_long_danger_count", 0))
                + int(risk.get("validation_short_danger_count", 0))
            ),
        })

        diagnostic = {
            "alpha_id": feature_spec.alpha_id,
            "family": feature_spec.family,
            "direction_type_train": direction_type,
            "dominant_side_train": dominant_side,
            "leverage_risk_profile": "10X_ONLY",
            "liquidation_model": "ADVERSE_MOVE_PROXY_NOT_EXACT_BINANCE_LIQUIDATION",
            "warning_adverse_move": warning_move,
            "danger_adverse_move": danger_move,
            **{f"combined_train_{k}": v for k, v in combined_train_beta.items()},
            **{f"combined_val_{k}": v for k, v in combined_val_beta.items()},
            **{f"long_train_{k}": v for k, v in sleeve_data["long"]["train_metrics"].items()},
            **{f"long_val_{k}": v for k, v in sleeve_data["long"]["val_metrics"].items()},
            **{f"short_train_{k}": v for k, v in sleeve_data["short"]["train_metrics"].items()},
            **{f"short_val_{k}": v for k, v in sleeve_data["short"]["val_metrics"].items()},
            **{f"long_train_{k}": v for k, v in sleeve_data["long"]["train_beta"].items()},
            **{f"long_val_{k}": v for k, v in sleeve_data["long"]["val_beta"].items()},
            **{f"short_train_{k}": v for k, v in sleeve_data["short"]["train_beta"].items()},
            **{f"short_val_{k}": v for k, v in sleeve_data["short"]["val_beta"].items()},
            **risk,
        }
        diagnostic_rows.append(diagnostic)

        factor_replay = {
            "schema_version": 1,
            "alpha_id": feature_spec.alpha_id,
            "family": feature_spec.family,
            "hypothesis": feature_spec.hypothesis,
            "direction_type_train": direction_type,
            "dominant_side_train": dominant_side,
            "leverage": 10,
            "liquidation_model": "10x adverse-price-move proxy; not exact Binance liquidation",
            "beta": {
                "train_btc": _json_value(combined_train_beta.get("beta_btc_daily")),
                "train_eth": _json_value(combined_train_beta.get("beta_eth_daily")),
                "train_residual_sharpe": _json_value(combined_train_beta.get("residual_sharpe_daily")),
                "validation_btc": _json_value(combined_val_beta.get("beta_btc_daily")),
                "validation_eth": _json_value(combined_val_beta.get("beta_eth_daily")),
                "validation_residual_sharpe": _json_value(combined_val_beta.get("residual_sharpe_daily")),
            },
            "events": events,
            "episodes": episodes,
        }
        (replay_dir / "factors" / f"{feature_spec.alpha_id}.json").write_text(
            json.dumps(factor_replay, separators=(",", ":"), ensure_ascii=False, default=_json_value),
            encoding="utf-8",
        )

        rows.append(row)

        for cost_bps in scenarios:
            scenario_return = gross - turnover * cost_bps / 10000.0
            for segment_name, segment_mask in (("train", train), ("validation", validation)):
                values = daily_metrics(
                    scenario_return[segment_mask], position[segment_mask], gross[segment_mask]
                )
                cost_rows.append({
                    "alpha_id": feature_spec.alpha_id,
                    "segment": segment_name,
                    "cost_bps_one_way": cost_bps,
                    **values,
                })

        del feature, position, gross, turnover, funding_pnl, base_returns
        for _s in sleeve_data.values():
            for _k in ("position", "gross", "turnover", "funding", "net"):
                _s.pop(_k, None)
        gc.collect()

    leaderboard = pd.DataFrame(rows).sort_values(
        ["phase2_candidate", "val_net_sharpe_daily"], ascending=[False, False]
    )
    cost_sensitivity = pd.DataFrame(cost_rows)
    yearly = pd.DataFrame(yearly_rows)

    factor_diagnostics = pd.DataFrame(diagnostic_rows)
    trade_ledger = pd.DataFrame(trade_rows)
    trade_events = pd.DataFrame(event_rows)

    leaderboard.to_csv(result_dir / "alpha_leaderboard.csv", index=False)
    cost_sensitivity.to_csv(result_dir / "cost_sensitivity.csv", index=False)
    yearly.to_csv(result_dir / "yearly_metrics.csv", index=False)
    factor_diagnostics.to_csv(result_dir / "factor_diagnostics.csv", index=False)
    trade_ledger.to_csv(result_dir / "trade_ledger.csv", index=False)
    trade_events.to_csv(result_dir / "trade_events.csv", index=False)

    replay_months = _write_market_replay(df, replay_dir, replay_bar_minutes)
    replay_index = {
        "schema_version": 1,
        "bar_minutes": replay_bar_minutes,
        "months": replay_months,
        "alphas": [
            {
                "alpha_id": r["alpha_id"],
                "family": r["family"],
                "direction_type_train": r.get("direction_type_train"),
                "dominant_side_train": r.get("dominant_side_train"),
            }
            for r in rows
        ],
        "test_locked": True,
        "visible_start": str(df.index.min()),
        "visible_end": str(df.index.max()),
    }
    (result_dir / "replay_index.json").write_text(
        json.dumps(replay_index, indent=2, ensure_ascii=False, default=_json_value),
        encoding="utf-8",
    )

    summary = {
        "schema_version": 2,
        "status": "PHASE2_LOW_TURNOVER_TRAIN_VALIDATION_ONLY",
        "test_locked": True,
        "test_start": str(validation_end),
        "visible_start": str(df.index.min()),
        "visible_end": str(df.index.max()),
        "rows_visible": int(len(df)),
        "alphas_researched": int(len(leaderboard)),
        "phase2_candidates": int(leaderboard["phase2_candidate"].sum()),
        "base_cost_bps_one_way": base_cost,
        "cost_scenarios_bps_one_way": scenarios,
        "funding_included": bool(cost_cfg.get("include_actual_funding", True)),
        "existing_factor_diagnostics_only": True,
        "new_alpha_logic_added": False,
        "leverage_risk_profile": "10X_ONLY",
        "liquidation_model": "ADVERSE_MOVE_PROXY_NOT_EXACT_BINANCE_LIQUIDATION",
        "replay_bar_minutes": replay_bar_minutes,
        "output_files": [
            "results/phase2_low_turnover/alpha_leaderboard.csv",
            "results/phase2_low_turnover/cost_sensitivity.csv",
            "results/phase2_low_turnover/yearly_metrics.csv",
            "results/phase2_low_turnover/factor_diagnostics.csv",
            "results/phase2_low_turnover/trade_ledger.csv",
            "results/phase2_low_turnover/trade_events.csv",
            "results/phase2_low_turnover/replay_index.json",
            "results/phase2_low_turnover/replay/",
        ],
    }
    (result_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=_json_value), encoding="utf-8"
    )
    return leaderboard, summary
