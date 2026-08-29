# One-time GitHub Pages Setup

目标：以后只打开一个固定网址看 BTCUSDT Quant Research Dashboard。

网站入口固定为：

`docs/index.html`

GitHub Pages 部署由：

`.github/workflows/deploy-pages.yml`

自动完成。

## 1. 在 GitHub 新建仓库

建议仓库名：

`BTCUSDT_Quant_Research_Kit`

创建空仓库即可，不要自动生成 README。

## 2. 在 VS Code 打开本项目根目录

确认终端是 PowerShell。

第一次执行：

```powershell
git init
git branch -M main
git add .
git commit -m "Initial BTCUSDT quant research dashboard"
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/BTCUSDT_Quant_Research_Kit.git
git push -u origin main
```

把 `<YOUR_GITHUB_USERNAME>` 替换为你的 GitHub 用户名。

如果你使用 SSH，也可以把 remote 改成 SSH 地址。

## 3. GitHub 开启 Pages

进入仓库：

`Settings → Pages`

在 `Build and deployment` 中：

`Source = GitHub Actions`

然后回到：

`Actions`

等待 `Deploy Quant Dashboard` 完成。

## 4. 固定网页地址

通常会是：

`https://<YOUR_GITHUB_USERNAME>.github.io/BTCUSDT_Quant_Research_Kit/`

以后网址不变。

## 5. 以后更新研究结果

研究脚本生成报告后：

```powershell
.\SYNC_DASHBOARD.ps1
.\PUBLISH_DASHBOARD.ps1 -Message "Update GenX research results"
```

或者 `run_demo.py` / 后续真实研究入口会直接同时更新：

- `reports/quant_research_dashboard.html`
- `docs/index.html`

因此正常研究结束后只需要：

```powershell
.\PUBLISH_DASHBOARD.ps1 -Message "Update research dashboard"
```

## 6. 重要安全原则

不要把下面内容提交到 GitHub：

- Binance API Key
- Binance Secret
- 私钥
- `.env`
- 大体积原始行情数据
- 任何账户交易凭证

网站只发布研究结果和静态图表，不发布交易密钥。
