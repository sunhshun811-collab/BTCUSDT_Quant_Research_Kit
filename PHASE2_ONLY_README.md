# Phase2 Only — Official Result Reset

Purpose: make the existing Codex-produced `phase2_low_turnover` result the **only official current research result**.

No backtest is rerun.

## Apply

Extract this ZIP directly over the existing project root:

`C:\Users\18871\Desktop\BTCUSDT_Quant_Research_Kit_web_v2`

Allow overwrite.

Then run in VS Code PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\MAKE_PHASE2_ONLY_OFFICIAL.ps1
```

## What it does

- Uses the already existing:
  - `results/phase2_low_turnover/`
  - `reports/phase2_low_turnover_dashboard.html`
- Removes current Phase1 result artifacts from the working tree.
- Resets `runs/` so the current research history starts from one official Phase2 run.
- Rebuilds `latest/` from Phase2 only.
- Sets `docs/index.html` to the Phase2 report.
- Writes `docs/OFFICIAL_RESEARCH_STATE.json`.
- Pushes the change to GitHub.
- Regenerates Desktop `research_package_latest.zip`.

Older experiments remain recoverable through Git commit history, but they are no longer treated as current or official results.

## Going forward

The desktop package will treat Phase2 as the official baseline and intentionally exclude Phase1 as a research result.
