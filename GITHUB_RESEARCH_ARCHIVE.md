# GitHub Research Archive v4

This patch makes the GitHub repository the primary research archive.

## First test — archive the Phase 1 result already on disk

After extracting this patch directly over the current project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\REGISTER_CURRENT_PHASE1.ps1 -Publish
```

This does **not** rerun the backtest. It archives the result already under `results/phase1/`, creates `RUN_0001_*`, updates `latest/`, commits, and pushes.

## Stable paths

- `latest/research_state.json`
- `latest/manifest.json`
- `latest/alpha_leaderboard.csv`
- `latest/data_quality.json`
- `latest/research_summary.md`

## Historical paths

- `runs/index.json`
- `runs/RUN_XXXX_.../manifest.json`
- `runs/RUN_XXXX_.../results/`
- `runs/RUN_XXXX_.../code_snapshot/`
- `runs/RUN_XXXX_.../research_summary.md`

## Future one-command workflow

Processed dataset already exists:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_RESEARCH_AND_PUBLISH.ps1
```

Refresh archives and rebuild dataset first:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_RESEARCH_AND_PUBLISH.ps1 -Download -RebuildDataset
```

Local run without push:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_RESEARCH_AND_PUBLISH.ps1 -NoPublish
```

## GitHub stores

Source code, configs, small CSV/JSON results, run manifests, data quality metadata, code snapshots, research summaries and Git history.

Raw Binance archives, large Parquet files, credentials and secrets remain local.
