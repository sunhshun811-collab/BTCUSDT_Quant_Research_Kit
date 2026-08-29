# v5 Phase 2 — Low-Turnover Alpha Research

这个补丁针对 Phase 1 的实际结果设计：18 个 Alpha 在单边 6 bps 成本后没有候选，绝大多数一分钟连续调仓信号被换手成本压垮。

## 安装

把 ZIP **直接解压到**：

`C:\Users\18871\Desktop\BTCUSDT_Quant_Research_Kit_web_v2`

允许合并 `src`、`configs` 和 `tests` 文件夹。本补丁只新增文件，不覆盖 Phase 1 研究结果，也不包含行情数据。

## 在 VS Code PowerShell 运行

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_PHASE2_LOW_TURNOVER.ps1 -SkipInstall -OpenReport
```

如果需要重新检查/安装依赖，去掉 `-SkipInstall`：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_PHASE2_LOW_TURNOVER.ps1 -OpenReport
```

## 输出

- `results/phase2_low_turnover/alpha_leaderboard.csv`
- `results/phase2_low_turnover/cost_sensitivity.csv`
- `results/phase2_low_turnover/yearly_metrics.csv`
- `results/phase2_low_turnover/summary.json`
- `reports/phase2_low_turnover_dashboard.html`

## 研究纪律

- Test 从加载阶段就排除，截止时间仍为 `2024-10-19 14:24 UTC`。
- 信号先延迟 1 根 K 线，再进行平滑、离散化和低频调仓。
- 加入实际资金费率：正资金费率时，多头支付、空头收取。
- 同时报告 0、2、6、10 bps 单边成本。
- IC / Rank IC 使用 15m、60m、240m 前瞻收益，而不是只看下一分钟。
- 候选还必须满足 Train 至少 75% 年度为正、Validation 所有可见年度区间为正，并限制 Train/Validation 最大回撤。
- 新结果单独写入 Phase 2 路径，不自动覆盖 GitHub Pages，也不自动提交或推送。

## 运行测试

```powershell
python -m unittest discover -s tests -p "test_phase2_low_turnover.py" -v
```

## 注意

Phase 2 候选仍只是研究筛选结果。不要因为 Validation 表现较好就解锁 Test；应先冻结因子公式、参数、成本模型和候选名单，再进行一次性 Test 评估。
