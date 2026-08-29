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
        "open_time", "close", "volume", "quote_volume", "trades",
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

    rows, cost_rows, yearly_rows = [], [], []
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
        gc.collect()

    leaderboard = pd.DataFrame(rows).sort_values(
        ["phase2_candidate", "val_net_sharpe_daily"], ascending=[False, False]
    )
    cost_sensitivity = pd.DataFrame(cost_rows)
    yearly = pd.DataFrame(yearly_rows)

    result_dir = output_root / "results" / "phase2_low_turnover"
    report_dir = output_root / "reports"
    result_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    leaderboard.to_csv(result_dir / "alpha_leaderboard.csv", index=False)
    cost_sensitivity.to_csv(result_dir / "cost_sensitivity.csv", index=False)
    yearly.to_csv(result_dir / "yearly_metrics.csv", index=False)

    summary = {
        "schema_version": 1,
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
        "output_files": [
            "results/phase2_low_turnover/alpha_leaderboard.csv",
            "results/phase2_low_turnover/cost_sensitivity.csv",
            "results/phase2_low_turnover/yearly_metrics.csv",
            "reports/phase2_low_turnover_dashboard.html",
        ],
    }
    (result_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=_json_value), encoding="utf-8"
    )

    from .phase2_report import build_phase2_report
    build_phase2_report(
        leaderboard, cost_sensitivity, yearly, summary,
        report_dir / "phase2_low_turnover_dashboard.html",
    )
    print(f"Saved: {result_dir}")
    print(f"Report: {report_dir / 'phase2_low_turnover_dashboard.html'}")
    return leaderboard, summary
