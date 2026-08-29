# v4.1 Machine-readable GitHub Pages mirror

Repository remains the authoritative archive:

`https://github.com/sunhshun811-collab/BTCUSDT_Quant_Research_Kit`

This patch additionally mirrors compact research artifacts to `docs/api/`.

After GitHub Pages deploys, stable URLs are:

- `https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/api/index.json`
- `https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/api/latest/research_state.json`
- `https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/api/latest/manifest.json`
- `https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/api/latest/research_summary.md`
- `https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/api/latest/alpha_leaderboard.csv`
- `https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/api/latest/data_quality.json`
- `https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/api/runs/index.json`

Historical compact run artifacts are mirrored under:

`/api/runs/<RUN_ID>/`

Raw Binance ZIP / Parquet files are never published.

## First sync

After extracting over the current project:

```powershell
powershell -ExecutionPolicy Bypass -File .\SYNC_RESEARCH_API_MIRROR.ps1 -Publish
```

No backtest rerun is required.
