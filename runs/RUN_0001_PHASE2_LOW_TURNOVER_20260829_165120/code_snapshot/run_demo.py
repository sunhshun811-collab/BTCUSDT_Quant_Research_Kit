
from pathlib import Path
import math, random
from datetime import datetime, timezone
from src.report_builder import render_report

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT = PROJECT_ROOT / "reports" / "quant_research_dashboard.html"
WEB_OUTPUT = PROJECT_ROOT / "docs" / "index.html"

random.seed(260829)
families = [
    ("DEMO_MOM_001","Momentum"),
    ("DEMO_MR_001","Mean Reversion"),
    ("DEMO_OF_001","Order Flow"),
    ("DEMO_VOL_001","Volatility"),
    ("DEMO_CARRY_001","Carry / Funding"),
    ("DEMO_LIQ_001","Liquidity"),
    ("DEMO_OI_001","OI / Positioning"),
    ("DEMO_RV_001","Relative Value"),
]

alphas=[]
for i,(aid,fam) in enumerate(families):
    alphas.append({
        "id": aid,
        "family": fam,
        "sharpe": 0.55 + 0.18*i + random.uniform(-0.15,0.15),
        "ic": 0.003 + 0.0017*i + random.uniform(-0.002,0.002),
        "rank_ic": 0.004 + 0.0015*i + random.uniform(-0.002,0.002),
        "mdd": -(0.06 + 0.012*i + random.uniform(0,0.025)),
        "turnover": 0.008 + 0.004*i + random.uniform(0,0.004),
    })

equity=[1.0]
for i in range(240):
    r = 0.00035 + 0.0015*math.sin(i/17) + random.gauss(0,0.0024)
    equity.append(equity[-1]*(1+r))

payload={
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "train_end": "2023-08-08 04:48 UTC",
    "val_end": "2024-10-19 14:24 UTC",
    "alphas": alphas,
    "equity_demo": equity,
}

render_report(payload, OUTPUT)
render_report(payload, WEB_OUTPUT)
print(f"Generated report: {OUTPUT}")
print(f"Updated website: {WEB_OUTPUT}")
