<!-- DASHBOARD_QUICK_LINK_START -->

# BTCUSDT Quant Research Kit

> ## 📊 [打开官方量化研究 Dashboard](https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/)
>
> **固定可视化入口：** [https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/](https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/)  
> 当前官方结果：**PHASE2_LOW_TURNOVER** · Test Locked

---

<!-- DASHBOARD_QUICK_LINK_END -->

This repository is the authoritative research archive and visualization project.

## Architecture

- `research/` — versioned mirror of the local research code/configuration. Raw market data is never committed.
- `official/latest/` — the only current official result (`PHASE2_LOW_TURNOVER`).
- `runs/` — immutable official research history.
- `site/` — GitHub-only visualization source.
- `.github/workflows/deploy-pages.yml` — GitHub Actions build/deploy pipeline.
- `tools/local_publisher/` — GitHub-side/local-cache synchronization tooling.

The Windows Desktop research workspace is intentionally compute-only and contains no dashboard, HTML, Pages, or visualization source code.

## Official visualization

https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/

The web site is built on GitHub Actions from `official/latest/`; no HTML is generated in the Desktop research folder.

## Official result policy

Only `PHASE2_LOW_TURNOVER` is the current official baseline. Earlier Phase1 experiments remain recoverable through Git history but are not part of the current official state.

