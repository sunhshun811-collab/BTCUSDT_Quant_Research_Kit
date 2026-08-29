
from __future__ import annotations
from pathlib import Path
import json, html
import pandas as pd

def _fmt(x,d=2):
    return "—" if pd.isna(x) else f"{x:.{d}f}"
def _pct(x,d=1):
    return "—" if pd.isna(x) else f"{x*100:.{d}f}%"

def build_phase1_html(project_root:Path,leaderboard:pd.DataFrame,summary:dict):
    qpath=project_root/"data"/"processed"/"data_quality.json"
    quality=json.loads(qpath.read_text(encoding="utf-8")) if qpath.exists() else {}
    body=[]
    for _,r in leaderboard.iterrows():
        cls="candidate" if bool(r.get("phase1_candidate")) else ""
        body.append(f"""<tr class="{cls}">
<td>{html.escape(str(r['alpha_id']))}</td><td>{html.escape(str(r['family']))}</td>
<td>{_fmt(r.get('train_net_sharpe_daily'))}</td><td><b>{_fmt(r.get('val_net_sharpe_daily'))}</b></td>
<td>{_fmt(r.get('val_ic_1m'),4)}</td><td>{_fmt(r.get('val_rank_ic_1m'),4)}</td>
<td>{_pct(r.get('val_max_drawdown'))}</td><td>{_fmt(r.get('val_avg_turnover_per_bar'),4)}</td>
<td>{'PASS' if bool(r.get('phase1_candidate')) else 'RESEARCH'}</td></tr>""")
    fq=quality.get("futures_btcusdt_1m",{})
    mq=quality.get("merged",{})
    doc=TEMPLATE
    repl={
        "{{ROWS}}":"\n".join(body),
        "{{ALPHAS}}":str(summary.get("alphas_researched",0)),
        "{{CANDIDATES}}":str(summary.get("phase1_candidates",0)),
        "{{DATA_ROWS}}":f"{summary.get('rows_visible',0):,}",
        "{{MISSING}}":str(fq.get("missing_minutes_between_endpoints","—")),
        "{{BTC_SPOT_MISSING}}":str(mq.get("btc_spot_missing","—")),
        "{{ETH_SPOT_MISSING}}":str(mq.get("eth_spot_missing","—")),
    }
    for k,v in repl.items(): doc=doc.replace(k,v)
    for folder,name in [(project_root/"docs","index.html"),(project_root/"reports","quant_research_dashboard.html")]:
        folder.mkdir(exist_ok=True); (folder/name).write_text(doc,encoding="utf-8")
    print("Updated fixed website:",project_root/"docs"/"index.html")

TEMPLATE=r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BTCUSDT Quant Research</title><style>
:root{--bg:#0b0f14;--p:#111922;--p2:#151f2a;--line:#263442;--t:#e9eef4;--m:#8fa2b5;--g:#68d391;--y:#f2c94c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t);font-family:Inter,system-ui,Segoe UI,Arial}.wrap{max-width:1500px;margin:auto;padding:24px}
h1{margin:0 0 6px}.sub{color:var(--m)}.top{display:flex;justify-content:space-between;gap:20px}.badge{font-size:11px;padding:5px 9px;border-radius:999px;border:1px solid #2d6547;background:#153121;color:var(--g);font-weight:700}.warn{border-color:#725d20;background:#2b240e;color:var(--y)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}.card,.box{background:var(--p);border:1px solid var(--line);border-radius:12px;padding:15px}.k{color:var(--m);font-size:12px;text-transform:uppercase}.v{font-size:25px;font-weight:800;margin-top:5px}
.note{margin-top:16px;background:#111922;border-left:3px solid var(--g);padding:14px;border-radius:8px;line-height:1.6}section{margin-top:18px}.title{font-weight:750;margin-bottom:9px}.split{display:grid;grid-template-columns:3fr 1fr 1fr;gap:4px}.split div{background:var(--p2);padding:12px;border-radius:8px;font-size:13px}.split b{display:block}
.table{overflow:auto;border:1px solid var(--line);border-radius:12px}table{border-collapse:collapse;width:100%;min-width:1000px;background:var(--p)}th,td{padding:10px 11px;border-bottom:1px solid var(--line);font-size:12px;text-align:right}th{color:var(--m);background:#0f161e;position:sticky;top:0}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}.candidate td{background:#11251b}
.quality{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.quality .box b{font-size:20px;display:block;margin-top:5px}.foot{color:var(--m);font-size:12px;margin:22px 0}@media(max-width:900px){.grid,.quality{grid-template-columns:1fr 1fr}.split{grid-template-columns:1fr}.top{display:block}}
</style></head><body><div class="wrap"><div class="top"><div><h1>BTCUSDT Quant Research</h1><div class="sub">Binance USD-M Perpetual · 1m · REAL Phase 1</div></div><div><span class="badge">TRAIN + VALIDATION</span> <span class="badge warn">TEST LOCKED</span></div></div>
<div class="note"><b>研究隔离：</b>Phase 1 在 2024-10-19 14:24 UTC 处物理截断数据。测试集 2024-10-19 14:24 → 2026-01-01 不参与筛选。本页指标来自真实 Train / Validation，而非 DEMO。</div>
<div class="grid"><div class="card"><div class="k">Real Alphas</div><div class="v">{{ALPHAS}}</div></div><div class="card"><div class="k">Phase1 Candidates</div><div class="v">{{CANDIDATES}}</div></div><div class="card"><div class="k">Visible 1m Rows</div><div class="v">{{DATA_ROWS}}</div></div><div class="card"><div class="k">Test Status</div><div class="v" style="color:var(--y)">LOCKED</div></div></div>
<section><div class="title">Strict chronological split</div><div class="split"><div><b>TRAIN · 60%</b>2020-01-01 00:00 → 2023-08-08 04:48 UTC</div><div><b>VALIDATION · 20%</b>2023-08-08 04:48 → 2024-10-19 14:24 UTC</div><div><b>TEST · 20%</b>2024-10-19 14:24 → 2026-01-01 00:00 UTC</div></div></section>
<section><div class="title">Data quality</div><div class="quality"><div class="box"><span class="k">Futures missing minutes</span><b>{{MISSING}}</b></div><div class="box"><span class="k">BTC spot join missing</span><b>{{BTC_SPOT_MISSING}}</b></div><div class="box"><span class="k">ETH spot join missing</span><b>{{ETH_SPOT_MISSING}}</b></div></div></section>
<section><div class="title">Alpha leaderboard · Net of configured fee + slippage</div><div class="table"><table><thead><tr><th>Alpha</th><th>Family</th><th>Train Sharpe</th><th>Validation Sharpe</th><th>Val IC 1m</th><th>Val Rank IC</th><th>Val MDD</th><th>Turnover/bar</th><th>Status</th></tr></thead><tbody>{{ROWS}}</tbody></table></div></section>
<div class="foot">Candidate = Validation daily-Sharpe ≥ 0.5 and Train/Validation Sharpe direction consistent. Screening only; Test remains untouched.</div></div></body></html>"""
