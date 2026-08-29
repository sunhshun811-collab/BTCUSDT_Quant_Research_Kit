# v3 Phase 1 — Real Binance Data + Alpha Baseline

把这个补丁 ZIP **直接解压到现有 `BTCUSDT_Quant_Research_Kit_web_v2` 项目根目录**，允许覆盖 `.gitignore` 和 `requirements.txt`。不要删除现有 `.git`。

## 一键运行

在 VS Code PowerShell、项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_PHASE1_CORE.ps1
```

第一次运行会完成：
1. 安装 Python 依赖；
2. 下载 Binance 公共历史 ZIP（可重跑续传，已有文件自动跳过）；
3. 构建真实 1m Parquet 数据；
4. 只使用 Train + Validation 跑第一批真实 Alpha；
5. 更新固定网站入口 `docs/index.html`。

第一次不自动发布。先双击/打开 `docs/index.html` 检查结果，然后：

```powershell
.\PUBLISH_DASHBOARD.ps1 -Message "Real Phase1 BTCUSDT alpha baseline"
```

## Core 数据源

- Binance USD-M BTCUSDT 永续 1m Klines
- Binance Spot BTCUSDT 1m Klines
- Binance Spot ETHUSDT 1m Klines
- Binance USD-M BTCUSDT Funding Rate

用于第一批：
Momentum、Mean Reversion、Taker Order Flow、Liquidity/Microstructure、Volatility、Funding/Crowding、Perp-Spot Relative Value、BTC Spot Beta Residual、BTC-vs-ETH Crypto Beta Residual。

## Test 硬锁

Phase 1 研究代码在 `2024-10-19 14:24 UTC` 直接截断 DataFrame，因此 Test (`2024-10-19 14:24 → 2026-01-01`) 不参与筛选。

## 下载中断

直接重新运行同一条一键命令即可，已完成的 ZIP 会跳过。

数据已经下载完、只想重跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_PHASE1_CORE.ps1 -SkipDownload
```

## Full 数据下载（Phase 2 预备）

```powershell
python .\download_phase1_data.py --mode full --workers 8
```

会额外下载 BTCUSDT Mark Price / Index Price / Premium Index 1m。Phase 1 暂不使用这些额外序列。
