
from pathlib import Path
import html

def render_report(payload: dict, output_path: str | Path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = ""
    for a in payload["alphas"]:
        rows += f"""
        <tr>
          <td>{html.escape(a['id'])}</td>
          <td>{html.escape(a['family'])}</td>
          <td>{a['sharpe']:.2f}</td>
          <td>{a['ic']:.4f}</td>
          <td>{a['rank_ic']:.4f}</td>
          <td>{a['mdd']:.2%}</td>
          <td>{a['turnover']:.4f}</td>
          <td><span class="badge demo">DEMO</span></td>
        </tr>"""

    points = ",".join(f"{v:.6f}" for v in payload["equity_demo"])
    doc = TEMPLATE.replace("{{ROWS}}", rows).replace("{{POINTS}}", points)
    doc = doc.replace("{{GENERATED_AT}}", payload["generated_at"])
    doc = doc.replace("{{TRAIN_END}}", payload["train_end"])
    doc = doc.replace("{{VAL_END}}", payload["val_end"])
    output_path.write_text(doc, encoding="utf-8")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>BTCUSDT Quant Research Dashboard</title>
<style>
:root{--bg:#0b0f14;--panel:#111820;--panel2:#151e28;--text:#e8eef5;--muted:#8fa1b3;--line:#253241;--good:#5fd38d;--warn:#ffcf5c;--accent:#69a7ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial}
.wrap{max-width:1420px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:18px}
h1{margin:0 0 6px;font-size:28px}.sub{color:var(--muted);font-size:14px}.badge{padding:3px 8px;border-radius:999px;font-size:11px;font-weight:700}
.demo{background:#3b2f11;color:var(--warn);border:1px solid #705b1c}.locked{background:#142d21;color:var(--good);border:1px solid #285b40}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.v{font-size:24px;margin-top:5px;font-weight:700}
section{margin-top:16px}.section-title{font-size:15px;font-weight:700;margin:0 0 10px}
.split{display:grid;grid-template-columns:3fr 1fr 1fr;gap:3px}.seg{padding:12px;border-radius:8px;background:var(--panel2);font-size:13px}.seg b{display:block;margin-bottom:3px}
.chart{height:260px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}
canvas{width:100%;height:220px}.tablebox{overflow:auto;border:1px solid var(--line);border-radius:12px}
table{width:100%;border-collapse:collapse;background:var(--panel);min-width:800px}th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:right;font-size:13px}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}th{color:var(--muted);font-weight:600;background:#0f161e}
.note{padding:14px;border-left:3px solid var(--warn);background:#17150d;color:#e7d998;border-radius:8px;font-size:13px;line-height:1.6}
.family-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.family{background:var(--panel);border:1px solid var(--line);padding:13px;border-radius:10px}.family b{display:block;margin-bottom:5px}.family span{color:var(--muted);font-size:12px}
footer{color:var(--muted);font-size:12px;margin:24px 0 10px}
@media(max-width:900px){.grid,.family-grid{grid-template-columns:1fr 1fr}.top{display:block}.split{grid-template-columns:1fr}}
</style>
</head>
<body><div class="wrap">
<div class="top">
<div><h1>BTCUSDT Quant Research Dashboard</h1><div class="sub">Binance USD-M Perpetual · 1 minute · 2020-01-01 → 2026-01-01</div></div>
<div><span class="badge demo">FRAMEWORK DEMO</span> <span class="badge locked">TEST LOCKED</span></div>
</div>
<div class="note"><b>重要：</b>当前收益、Sharpe、IC 和回撤均为框架验证用的 DEMO 数据，不是 BTCUSDT 真实历史回测结果。真实数据接入后将替换此区域。</div>

<section><div class="grid">
<div class="card"><div class="k">Research Families</div><div class="v">8</div></div>
<div class="card"><div class="k">Demo Alphas</div><div class="v">8</div></div>
<div class="card"><div class="k">Bar Interval</div><div class="v">1m</div></div>
<div class="card"><div class="k">Test Status</div><div class="v" style="color:var(--good)">LOCKED</div></div>
</div></section>

<section>
<div class="section-title">Strict chronological 6:2:2 split</div>
<div class="split">
<div class="seg"><b>TRAIN · 60%</b>2020-01-01 00:00 UTC → {{TRAIN_END}}</div>
<div class="seg"><b>VALIDATION · 20%</b>{{TRAIN_END}} → {{VAL_END}}</div>
<div class="seg"><b>TEST · 20%</b>{{VAL_END}} → 2026-01-01 00:00 UTC</div>
</div>
</section>

<section><div class="section-title">Demo equity curve · pipeline verification only</div><div class="chart"><canvas id="eq"></canvas></div></section>

<section>
<div class="section-title">Alpha leaderboard · DEMO</div>
<div class="tablebox"><table>
<thead><tr><th>Alpha ID</th><th>Family</th><th>Net Sharpe</th><th>IC</th><th>Rank IC</th><th>MDD</th><th>Turnover/bar</th><th>Status</th></tr></thead>
<tbody>{{ROWS}}</tbody>
</table></div>
</section>

<section>
<div class="section-title">Research family map</div>
<div class="family-grid">
<div class="family"><b>Momentum / Trend</b><span>multi-horizon return, breakout, trend persistence</span></div>
<div class="family"><b>Mean Reversion</b><span>z-score, VWAP deviation, short-term reversal</span></div>
<div class="family"><b>Order Flow</b><span>taker imbalance, trade intensity, signed volume proxy</span></div>
<div class="family"><b>Volatility</b><span>realized vol, range, vol-of-vol, expansion/compression</span></div>
<div class="family"><b>Carry / Funding</b><span>funding, premium, mark-index basis</span></div>
<div class="family"><b>Liquidity</b><span>volume shock, impact proxy, average trade size</span></div>
<div class="family"><b>OI / Positioning</b><span>OI change, crowding, OI × return/funding</span></div>
<div class="family"><b>Relative Value</b><span>perp-spot, BTC-ETH residual, beta-neutral residual</span></div>
</div>
</section>

<footer>Generated: {{GENERATED_AT}} · v1 framework · No test-set optimization permitted.</footer>
</div>
<script>
const data=[{{POINTS}}];
const c=document.getElementById('eq'),ctx=c.getContext('2d');
function draw(){
 const dpr=window.devicePixelRatio||1,rect=c.getBoundingClientRect();
 c.width=rect.width*dpr;c.height=rect.height*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);
 const w=rect.width,h=rect.height,p=22;
 ctx.clearRect(0,0,w,h);ctx.strokeStyle='#253241';ctx.lineWidth=1;
 for(let i=0;i<5;i++){let y=p+(h-2*p)*i/4;ctx.beginPath();ctx.moveTo(p,y);ctx.lineTo(w-p,y);ctx.stroke()}
 let mn=Math.min(...data),mx=Math.max(...data),rng=mx-mn||1;
 ctx.strokeStyle='#69a7ff';ctx.lineWidth=2;ctx.beginPath();
 data.forEach((v,i)=>{let x=p+(w-2*p)*i/(data.length-1);let y=h-p-(h-2*p)*(v-mn)/rng;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)});
 ctx.stroke();
}
draw();window.addEventListener('resize',draw);
</script>
</body></html>"""
