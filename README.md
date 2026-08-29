# BTCUSDT Quant Research Kit — Web Dashboard v2

这是 BTCUSDT Binance USD-M 永续合约 1min 量化研究框架的“固定网址 Dashboard”版本。

## 核心变化

- `docs/index.html` 是长期固定网页入口。
- 每次研究后只更新同一个网页，不再生成一堆独立网页。
- `.github/workflows/deploy-pages.yml` 负责自动部署 GitHub Pages。
- `PUBLISH_DASHBOARD.ps1` 负责在 VS Code PowerShell 中一键提交并推送最新 Dashboard。
- `SYNC_DASHBOARD.ps1` 把本地研究报告同步到固定网站入口。
- 原始数据和 API 密钥默认不会进入 Git 仓库。

## 网站工作流

研究：

```powershell
python .\run_demo.py
```

发布：

```powershell
.\PUBLISH_DASHBOARD.ps1 -Message "Update research dashboard"
```

之后直接刷新固定 GitHub Pages URL 即可查看最新结果。

## 当前状态

当前网页中的 Alpha / Sharpe / IC / Equity Curve 仍然是 DEMO 数据，仅用于验证整个网页和发布流程。

正式研究需要接入真实 BTCUSDT 2020-01-01 至 2026-01-01 1min 数据。

## 数据切分

- Train: 2020-01-01 00:00 UTC → 2023-08-08 04:48 UTC
- Validation: 2023-08-08 04:48 UTC → 2024-10-19 14:24 UTC
- Test: 2024-10-19 14:24 UTC → 2026-01-01 00:00 UTC
- Test locked: YES

## 第一次上线

查看：

`SETUP_GITHUB_PAGES.md`
