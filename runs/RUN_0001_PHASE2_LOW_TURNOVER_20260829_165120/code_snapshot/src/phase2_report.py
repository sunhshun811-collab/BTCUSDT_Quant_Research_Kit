from __future__ import annotations

from pathlib import Path
import html

import pandas as pd


def _number(value, digits=2):
    return "—" if pd.isna(value) else f"{float(value):.{digits}f}"


def _percent(value, digits=1):
    return "—" if pd.isna(value) else f"{float(value) * 100:.{digits}f}%"


def build_phase2_report(
    leaderboard: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    yearly: pd.DataFrame,
    summary: dict,
    output_path: Path,
):
    table_rows = []
    for _, row in leaderboard.iterrows():
        css_class = "candidate" if bool(row.get("phase2_candidate")) else ""
        table_rows.append(
            f"<tr class='{css_class}'>"
            f"<td>{html.escape(str(row['alpha_id']))}</td>"
            f"<td>{html.escape(str(row['family']))}</td>"
            f"<td>{int(row['rebalance_minutes'])}</td>"
            f"<td>{_number(row.get('train_net_sharpe_daily'))}</td>"
            f"<td><b>{_number(row.get('val_net_sharpe_daily'))}</b></td>"
            f"<td>{_percent(row.get('val_net_return'))}</td>"
            f"<td>{_percent(row.get('val_max_drawdown'))}</td>"
            f"<td>{_number(row.get('val_rank_ic_60m'), 4)}</td>"
            f"<td>{_number(row.get('val_annualized_turnover'), 1)}</td>"
            f"<td>{_percent(row.get('train_positive_year_fraction'), 0)}</td>"
            f"<td>{_percent(row.get('val_positive_year_fraction'), 0)}</td>"
            f"<td>{'PASS' if bool(row.get('phase2_candidate')) else 'RESEARCH'}</td>"
            "</tr>"
        )

    validation_cost = cost_sensitivity[cost_sensitivity["segment"] == "validation"].copy()
    pivot = validation_cost.pivot_table(
        index="alpha_id", columns="cost_bps_one_way", values="net_sharpe_daily", aggfunc="first"
    )
    cost_rows = []
    for alpha_id in leaderboard.head(10)["alpha_id"]:
        cells = "".join(
            f"<td>{_number(pivot.loc[alpha_id, cost]) if alpha_id in pivot.index and cost in pivot.columns else '—'}</td>"
            for cost in sorted(pivot.columns)
        )
        cost_rows.append(f"<tr><td>{html.escape(str(alpha_id))}</td>{cells}</tr>")
    cost_headers = "".join(f"<th>{float(cost):g} bps</th>" for cost in sorted(pivot.columns))

    html_doc = f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>BTCUSDT Phase 2 Low-Turnover Research</title>
<style>
:root{{--bg:#0b0f14;--panel:#111922;--line:#263442;--text:#e9eef4;--muted:#8fa2b5;--green:#68d391;--yellow:#f2c94c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,Segoe UI,Arial}}
.wrap{{max-width:1500px;margin:auto;padding:24px}}h1{{margin:0 0 5px}}.muted{{color:var(--muted)}}
.badges{{margin:12px 0}}.badge{{display:inline-block;margin-right:7px;padding:5px 9px;border-radius:999px;border:1px solid #2d6547;background:#153121;color:var(--green);font-size:11px;font-weight:700}}
.warn{{border-color:#725d20;background:#2b240e;color:var(--yellow)}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}}
.card,.note{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px}}.k{{color:var(--muted);font-size:12px;text-transform:uppercase}}.v{{font-size:25px;font-weight:800;margin-top:5px}}
.note{{line-height:1.65;border-left:3px solid var(--green)}}section{{margin-top:20px}}h2{{font-size:16px}}
.table{{overflow:auto;border:1px solid var(--line);border-radius:12px}}table{{border-collapse:collapse;width:100%;min-width:1000px;background:var(--panel)}}
th,td{{padding:10px;border-bottom:1px solid var(--line);font-size:12px;text-align:right}}th{{position:sticky;top:0;background:#0f161e;color:var(--muted)}}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}.candidate td{{background:#11251b}}
@media(max-width:850px){{.grid{{grid-template-columns:1fr 1fr}}}}
</style></head><body><div class='wrap'>
<h1>BTCUSDT Phase 2 · Low-Turnover Research</h1>
<div class='muted'>Binance USD-M Perpetual · 1m source bars · slower execution and multi-horizon evaluation</div>
<div class='badges'><span class='badge'>TRAIN + VALIDATION</span><span class='badge warn'>TEST PHYSICALLY LOCKED</span></div>
<div class='note'><b>本轮修正：</b>信号先延迟一根 K 线，再平滑、离散化并按 15–60 分钟调仓；结果包含实际资金费率与 0/2/6/10 bps 单边成本情景。测试集仍未读取。</div>
<div class='grid'>
<div class='card'><div class='k'>Alphas</div><div class='v'>{summary['alphas_researched']}</div></div>
<div class='card'><div class='k'>Candidates</div><div class='v'>{summary['phase2_candidates']}</div></div>
<div class='card'><div class='k'>Visible rows</div><div class='v'>{summary['rows_visible']:,}</div></div>
<div class='card'><div class='k'>Base one-way cost</div><div class='v'>{summary['base_cost_bps_one_way']:g} bps</div></div>
</div>
<section><h2>Alpha leaderboard · base cost after funding</h2><div class='table'><table><thead><tr>
<th>Alpha</th><th>Family</th><th>Rebal min</th><th>Train Sharpe</th><th>Val Sharpe</th><th>Val Return</th><th>Val MDD</th><th>Val Rank IC 60m</th><th>Annual Turnover</th><th>Train +Years</th><th>Val +Years</th><th>Status</th>
</tr></thead><tbody>{''.join(table_rows)}</tbody></table></div></section>
<section><h2>Top 10 validation Sharpe · cost sensitivity</h2><div class='table'><table><thead><tr><th>Alpha</th>{cost_headers}</tr></thead><tbody>{''.join(cost_rows)}</tbody></table></div></section>
<p class='muted'>Candidate requires positive Train Sharpe, Validation Sharpe ≥ 0.5, positive Validation return, Train/Validation MDD ≥ -35%, at least 75% positive Train years, all visible Validation calendar periods positive, and consistent Train/Validation direction. This is screening, not investment advice.</p>
</div></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")
