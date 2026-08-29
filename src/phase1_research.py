
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd

TRAIN_END = pd.Timestamp("2023-08-08T04:48:00Z")
VAL_END = pd.Timestamp("2024-10-19T14:24:00Z")
START = pd.Timestamp("2020-01-01T00:00:00Z")

def zscore(s: pd.Series, n: int) -> pd.Series:
    mu = s.rolling(n,min_periods=n).mean()
    sd = s.rolling(n,min_periods=n).std(ddof=0).replace(0,np.nan)
    return (s-mu)/sd

def rolling_beta(y: pd.Series, x: pd.Series, n: int) -> pd.Series:
    return y.rolling(n,min_periods=n).cov(x) / x.rolling(n,min_periods=n).var(ddof=1).replace(0,np.nan)

def build_features(df):
    c = df["close"].astype(float)
    r = np.log(c).diff()
    out, meta = pd.DataFrame(index=df.index), {}
    def add(name,s,fam,h):
        out[name]=s; meta[name]={"family":fam,"hypothesis":h}

    for n in (15,60,240):
        add(f"MOM_{n:03d}",np.log(c).diff(n),"Momentum / Trend",f"{n}m directional persistence.")
        add(f"MR_Z_{n:03d}",-zscore(np.log(c),n),"Mean Reversion",f"{n}m price dislocation reversion.")

    vol=df["volume"].replace(0,np.nan).astype(float)
    imb=(2*df["taker_buy_base"].astype(float)-vol)/vol
    add("OFI_001",imb,"Order Flow","Aggressive taker imbalance contains information.")
    add("OFI_020",imb.rolling(20).mean(),"Order Flow","Persistent taker imbalance contains information.")
    add("OFI_060",imb.rolling(60).mean(),"Order Flow","Sustained taker imbalance captures informed pressure.")

    trades=df["trades"].replace(0,np.nan).astype(float)
    avg_trade=df["quote_volume"].astype(float)/trades
    add("TRADE_SIZE_SHOCK_060",zscore(np.log1p(avg_trade),60),"Liquidity / Microstructure","Abnormal average trade size proxies urgent/informed flow.")

    dollar=df["quote_volume"].replace(0,np.nan).astype(float)
    amihud=r.abs()/dollar
    add("ILLIQ_MR_240",-zscore(np.log1p(amihud*1e9),240),"Liquidity / Microstructure","Extreme short-horizon impact partially normalizes.")
    add("VOLUME_SHOCK_240",zscore(np.log1p(dollar),240)*np.sign(r),"Liquidity / Microstructure","Directional volume shock captures informed flow.")

    rv60=r.rolling(60).std(ddof=0)
    add("VOL_EXP_MOM_060",zscore(rv60,240)*np.sign(np.log(c).diff(15)),"Volatility","Trend continuation strengthens in volatility expansion.")

    if "funding_rate" in df:
        add("FUNDING_CROWDING_MR",-zscore(df["funding_rate"].astype(float),30*24*60),"Carry / Funding","Extreme funding proxies crowded positioning.")

    if "btc_spot_close" in df:
        spot=df["btc_spot_close"].astype(float)
        basis=np.log(c)-np.log(spot)
        add("PERP_SPOT_BASIS_MR",-zscore(basis,1440),"Relative Value","Abnormal perp-vs-spot basis mean reverts.")
        sr=np.log(spot).diff()
        beta=rolling_beta(r,sr,1440)
        resid=r-beta*sr
        add("BTC_BETA_RESID_MR_060",-resid.rolling(60).sum(),"Beta / Residual","Contract-specific beta-neutral residual mean reverts.")
        add("BTC_BETA_RESID_MOM_240",resid.rolling(240).sum(),"Beta / Residual","Persistent beta-neutral residual can trend.")

    if "btc_spot_close" in df and "eth_spot_close" in df:
        br=np.log(df["btc_spot_close"].astype(float)).diff()
        er=np.log(df["eth_spot_close"].astype(float)).diff()
        beta=rolling_beta(br,er,1440)
        resid=br-beta*er
        add("BTC_ETH_RESID_MR_060",-resid.rolling(60).sum(),"Beta / Residual","BTC residual versus ETH crypto-beta mean reverts.")

    return out.replace([np.inf,-np.inf],np.nan),meta

def signal_from_feature(f,lookback=1440,clip=3.0):
    return (zscore(f,lookback).clip(-clip,clip)/clip).clip(-1,1)

def daily_sharpe(r):
    d=r.resample("1D").sum().dropna()
    if len(d)<10:return np.nan
    sd=d.std(ddof=1)
    return float(d.mean()/sd*np.sqrt(365.25)) if sd>0 else 0.0

def metrics(ret,pos,feature,close):
    xret=ret.dropna()
    if xret.empty:return {}
    eq=(1+xret).cumprod()
    dd=eq/eq.cummax()-1
    fwd=close.pct_change().shift(-1)
    x=pd.concat([feature.rename("f"),fwd.rename("r")],axis=1).dropna()
    return {
        "bars":int(len(xret)),
        "net_return":float(eq.iloc[-1]-1),
        "net_sharpe_daily":daily_sharpe(xret),
        "max_drawdown":float(dd.min()),
        "ic_1m":float(x["f"].corr(x["r"])) if len(x)>=100 else np.nan,
        "rank_ic_1m":float(x["f"].rank().corr(x["r"].rank())) if len(x)>=100 else np.nan,
        "avg_turnover_per_bar":float(pos.diff().abs().mean()),
        "mean_abs_position":float(pos.abs().mean()),
    }

def run_phase1(project_root:Path):
    cfg=json.loads((project_root/"configs"/"phase1_real_research.json").read_text(encoding="utf-8"))
    path=project_root/"data"/"processed"/"btc_core_1m_2020_2025.parquet"
    df=pd.read_parquet(path)
    df["open_time"]=pd.to_datetime(df["open_time"],utc=True)
    df=df.set_index("open_time").sort_index()
    # HARD TEST LOCK: nothing at or after VAL_END is visible.
    df=df[(df.index>=START)&(df.index<VAL_END)].copy()
    print(f"Visible rows: {len(df):,} | {df.index.min()} -> {df.index.max()}")
    print("TEST SET IS PHYSICALLY EXCLUDED FROM PHASE1.")

    feats,meta=build_features(df)
    close=df["close"].astype(float)
    market=close.pct_change().fillna(0)
    cost=(cfg["costs"]["fee_bps_one_way"]+cfg["costs"]["slippage_bps_one_way"])/10000.0
    train=df.index<TRAIN_END
    val=(df.index>=TRAIN_END)&(df.index<VAL_END)

    rows=[]
    for name in feats.columns:
        raw=feats[name]
        desired=signal_from_feature(raw,cfg["signal"]["zscore_lookback"],cfg["signal"]["clip_z"])
        pos=desired.shift(1).fillna(0)
        turnover=pos.diff().abs().fillna(pos.abs())
        strat=pos*market-turnover*cost
        tr=metrics(strat[train],pos[train],raw[train],close[train])
        va=metrics(strat[val],pos[val],raw[val],close[val])
        rows.append({
            "alpha_id":name,"family":meta[name]["family"],"hypothesis":meta[name]["hypothesis"],
            **{f"train_{k}":v for k,v in tr.items()},
            **{f"val_{k}":v for k,v in va.items()},
        })

    res=pd.DataFrame(rows)
    res["direction_consistent"]=np.sign(res["train_net_sharpe_daily"].fillna(0))==np.sign(res["val_net_sharpe_daily"].fillna(0))
    res["phase1_candidate"]=(res["val_net_sharpe_daily"]>=cfg["acceptance_preview"]["validation_net_sharpe_min"])&res["direction_consistent"]
    res=res.sort_values(["phase1_candidate","val_net_sharpe_daily"],ascending=[False,False])

    out=project_root/"results"/"phase1"; out.mkdir(parents=True,exist_ok=True)
    res.to_csv(out/"alpha_leaderboard.csv",index=False)
    summary={
        "status":"REAL_PHASE1_TRAIN_VALIDATION_ONLY","test_locked":True,
        "test_start":str(VAL_END),"rows_visible":int(len(df)),
        "alphas_researched":int(len(res)),"phase1_candidates":int(res["phase1_candidate"].sum()),
        "families":sorted(res["family"].unique().tolist())
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(res[["alpha_id","family","train_net_sharpe_daily","val_net_sharpe_daily","val_ic_1m","phase1_candidate"]].to_string(index=False))
    return res,summary
