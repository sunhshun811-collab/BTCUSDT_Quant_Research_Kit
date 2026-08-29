# v5 Validation Preview

该补丁已在桌面项目现有的 `btc_core_1m_2020_2025.parquet` 上完整运行验证。

- 可见区间：2020-01-01 00:00 UTC → 2024-10-19 14:23 UTC
- 可见行数：2,525,184
- Test 起点：2024-10-19 14:24 UTC
- Test 状态：物理排除，未读取
- 研究因子：17
- 严格候选：1
- 本机完整运行耗时：约 65 秒（不含依赖安装）

## 严格候选

`LT_FUNDING_CROWDING_MR_30D`

- Train 日频 Sharpe：1.1875
- Validation 日频 Sharpe：1.7711
- Train 最大回撤：-20.03%
- Validation 最大回撤：-14.10%
- Validation 净收益：34.60%
- Validation 年化换手：63.23
- Validation 60m Rank IC：0.0021
- 单边 10 bps 成本下 Validation Sharpe：1.5979
- Train 四个日历年度区间全部为正
- Validation 两个可见日历年度区间全部为正

## 观察名单（未通过严格候选规则）

- `LT_PERP_SPOT_BASIS_MR_43200`：整体 Train/Validation 较强，但 Validation 的 2023 可见区间略为负收益。
- `LT_MOM_4320`：Validation 表现较好，但 Train 最大回撤约 -56.5%，且 2021 年为负。
- `LT_TRADE_SIZE_DIR_0240`：Validation Sharpe 约 0.69，但 Train 年度稳定性不足。

这些结果仍然使用了 Validation 进行筛选，不能视为最终样本外证明。下一步应冻结公式和执行参数，再决定是否进行一次性的 Test 评估。
