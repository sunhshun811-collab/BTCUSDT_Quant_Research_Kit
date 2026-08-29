
from __future__ import annotations
from pathlib import Path
import json, zipfile
import numpy as np
import pandas as pd

KLINE_COLS = [
    "open_time","open","high","low","close","volume",
    "close_time","quote_volume","trades",
    "taker_buy_base","taker_buy_quote","ignore"
]
FUNDING_COLS = ["calc_time","funding_interval_hours","last_funding_rate"]

def _read_csv_member(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        members = [x for x in zf.namelist() if x.lower().endswith(".csv")]
        if not members:
            raise ValueError(f"No CSV in {zip_path}")
        with zf.open(members[0]) as f:
            return pd.read_csv(f, header=None, low_memory=False)

def _to_utc_timestamp(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    valid = x.dropna()
    if valid.empty:
        return pd.to_datetime(x, unit="ms", utc=True, errors="coerce")
    mag = float(valid.abs().median())
    unit = "us" if mag >= 1e14 else ("ms" if mag >= 1e11 else "s")
    return pd.to_datetime(x, unit=unit, utc=True, errors="coerce")

def read_kline_zip(zip_path: Path, keep: list[str]) -> pd.DataFrame:
    df = _read_csv_member(zip_path)
    if df.shape[1] < 12:
        raise ValueError(f"Unexpected kline schema ({df.shape[1]} cols): {zip_path}")
    df = df.iloc[:, :12]
    df.columns = KLINE_COLS
    df["open_time"] = _to_utc_timestamp(df["open_time"])
    df = df[df["open_time"].notna()].copy()
    for c in keep:
        if c != "open_time":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[keep].drop_duplicates("open_time").sort_values("open_time")

def read_funding_zip(zip_path: Path) -> pd.DataFrame:
    df = _read_csv_member(zip_path)
    if df.shape[1] < 3:
        raise ValueError(f"Unexpected funding schema ({df.shape[1]} cols): {zip_path}")
    df = df.iloc[:, :3]
    df.columns = FUNDING_COLS
    df["calc_time"] = _to_utc_timestamp(df["calc_time"])
    df["funding_interval_hours"] = pd.to_numeric(df["funding_interval_hours"], errors="coerce")
    df["last_funding_rate"] = pd.to_numeric(df["last_funding_rate"], errors="coerce")
    return df[df["calc_time"].notna()].drop_duplicates("calc_time").sort_values("calc_time")

def _concat_source(folder: Path, kind: str, keep=None) -> pd.DataFrame:
    zips = sorted(folder.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"No Binance archives found in {folder}")
    frames = []
    for i, zp in enumerate(zips, 1):
        part = read_funding_zip(zp) if kind == "funding" else read_kline_zip(zp, keep)
        frames.append(part)
        if i % 12 == 0 or i == len(zips):
            print(f"  parsed {i}/{len(zips)} {folder.name}")
    key = "calc_time" if kind == "funding" else "open_time"
    return pd.concat(frames, ignore_index=True).drop_duplicates(key).sort_values(key)

def _quality(df: pd.DataFrame, ts_col="open_time") -> dict:
    s = pd.DatetimeIndex(df[ts_col].dropna().sort_values().unique())
    if len(s) < 2:
        return {"rows":int(len(df)), "missing_minutes_between_endpoints":None}
    expected = int((s[-1] - s[0]).total_seconds() // 60) + 1
    return {
        "rows":int(len(df)),
        "unique_timestamps":int(len(s)),
        "start":str(s[0]), "end":str(s[-1]),
        "expected_minutes_between_endpoints":expected,
        "missing_minutes_between_endpoints":int(max(expected-len(s),0)),
        "duplicate_timestamps":int(df[ts_col].duplicated().sum()),
    }

def build_core_dataset(project_root: Path):
    raw = project_root/"data"/"raw"/"binance"
    processed = project_root/"data"/"processed"
    processed.mkdir(parents=True, exist_ok=True)

    print("Parsing futures BTCUSDT 1m...")
    fut = _concat_source(raw/"futures_btcusdt_1m","kline",
        ["open_time","open","high","low","close","volume","quote_volume",
         "trades","taker_buy_base","taker_buy_quote"])
    print("Parsing spot BTCUSDT 1m...")
    btc = _concat_source(raw/"spot_btcusdt_1m","kline",["open_time","close"]).rename(columns={"close":"btc_spot_close"})
    print("Parsing spot ETHUSDT 1m...")
    eth = _concat_source(raw/"spot_ethusdt_1m","kline",["open_time","close"]).rename(columns={"close":"eth_spot_close"})
    print("Parsing BTCUSDT funding...")
    funding = _concat_source(raw/"funding_btcusdt","funding")

    start = pd.Timestamp("2020-01-01T00:00:00Z")
    end = pd.Timestamp("2026-01-01T00:00:00Z")
    fut = fut[(fut.open_time>=start)&(fut.open_time<end)].copy()
    btc = btc[(btc.open_time>=start)&(btc.open_time<end)].copy()
    eth = eth[(eth.open_time>=start)&(eth.open_time<end)].copy()
    funding = funding[(funding.calc_time>=start)&(funding.calc_time<end)].copy()

    quality = {
        "futures_btcusdt_1m":_quality(fut),
        "spot_btcusdt_1m":_quality(btc),
        "spot_ethusdt_1m":_quality(eth),
        "funding_rows":int(len(funding)),
    }

    print("Merging core data...")
    master = fut.merge(btc,on="open_time",how="left",validate="one_to_one")
    master = master.merge(eth,on="open_time",how="left",validate="one_to_one")
    master = pd.merge_asof(
        master.sort_values("open_time"),
        funding.rename(columns={"calc_time":"funding_time"}).sort_values("funding_time"),
        left_on="open_time", right_on="funding_time",
        direction="backward", allow_exact_matches=True
    )
    master["funding_event"] = master["open_time"].eq(master["funding_time"])
    master["funding_rate"] = master["last_funding_rate"]

    quality["merged"] = {
        "rows":int(len(master)),
        "btc_spot_missing":int(master["btc_spot_close"].isna().sum()),
        "eth_spot_missing":int(master["eth_spot_close"].isna().sum()),
        "funding_rate_missing":int(master["funding_rate"].isna().sum()),
    }

    out = processed/"btc_core_1m_2020_2025.parquet"
    master.sort_values("open_time").reset_index(drop=True).to_parquet(out,index=False,compression="zstd")
    funding.to_parquet(processed/"btc_funding_2020_2025.parquet",index=False,compression="zstd")
    (processed/"data_quality.json").write_text(json.dumps(quality,indent=2),encoding="utf-8")
    print("Saved:", out)
    return out, quality
