# v4.2 Desktop Research Package

完全不依赖 Codex。

把本补丁直接解压覆盖到现有项目根目录：

`C:\Users\18871\Desktop\BTCUSDT_Quant_Research_Kit_web_v2`

允许覆盖 `RUN_RESEARCH_AND_PUBLISH.ps1`，不要删除 `.git`。

## 现在就测试：不重新跑回测

在 VS Code PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\BUILD_RESEARCH_PACKAGE.ps1
```

它会直接在 Windows 桌面生成：

`research_package_latest.zip`

然后把这个 ZIP 拖进 ChatGPT 即可。

## 以后正常的一键研究

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_RESEARCH_AND_PUBLISH.ps1
```

自动完成：

研究 → 新建历史 Run → 更新 latest → 更新 GitHub → 桌面生成 `research_package_latest.zip`

如果需要重新下载 Binance 数据并重建 Parquet：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_RESEARCH_AND_PUBLISH.ps1 -Download -RebuildDataset
```

如果只想本地运行，不 push GitHub：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_RESEARCH_AND_PUBLISH.ps1 -NoPublish
```

## ZIP 包含

- `latest/`
- 最新历史 `runs/RUN_XXXX.../` 的完整紧凑档案和代码快照
- `results/phase1/`
- `src/`
- `configs/`
- `alphas/`
- 相关根目录 Python / PowerShell 文件
- `docs/index.html`
- Git 当前 commit / branch / status
- 最近 20 次 Git log
- staged / unstaged diff
- 每个文件 SHA256

明确不包含：

- `data/raw/`
- `data/processed/`
- Parquet
- Binance 原始 ZIP
- 超过 20MB 的单文件
- `.git` 内部对象
- 密钥与凭证
