# Official BTCUSDT Research Result

- Policy: **PHASE2 ONLY**
- Phase: `PHASE2_LOW_TURNOVER`
- Run: `RUN_0001_PHASE2_LOW_TURNOVER_20260829_165120`
- Test locked: `True`
- Alpha count: `17`

All previous Phase1 baseline outputs are deprecated and are not part of the current official result.
They remain available only through Git history.

## Top validation results

| Alpha | Family | Train Sharpe | Validation Sharpe | Candidate |
|---|---|---:|---:|---|
| LT_FUNDING_CROWDING_MR_30D | Carry / Funding | 1.187 | 1.771 | True |
| LT_PERP_SPOT_BASIS_MR_43200 | Relative Value | 1.574 | 1.225 | False |
| LT_MOM_4320 | Momentum / Trend | 0.354 | 1.048 | False |
| LT_TRADE_SIZE_DIR_0240 | Liquidity / Microstructure | 0.103 | 0.686 | False |
| LT_VOLUME_CONFIRMED_MOM_0720 | Liquidity / Microstructure | 0.299 | 0.315 | False |
| LT_ILLIQ_MR_1440 | Liquidity / Microstructure | 0.046 | 0.237 | False |
| LT_MOM_0720 | Momentum / Trend | 0.307 | 0.234 | False |
| LT_BTC_ETH_RATIO_MR_7D | Relative Value | -0.482 | 0.106 | False |
| LT_VOL_ADJ_MOM_0720 | Volatility | 0.699 | 0.045 | False |
| LT_MOM_0240 | Momentum / Trend | -0.292 | -0.175 | False |
| LT_PERP_SPOT_BASIS_MR_10080 | Relative Value | 1.068 | -0.294 | False |
| LT_BTC_ETH_RATIO_MOM_1D | Relative Value | 0.048 | -0.815 | False |
| LT_MOM_1440 | Momentum / Trend | -0.122 | -0.871 | False |
| LT_MR_Z_1440 | Mean Reversion | -0.730 | -1.061 | False |
| LT_OFI_0720 | Order Flow | 0.892 | -1.092 | False |
| LT_MR_Z_0240 | Mean Reversion | -1.144 | -2.719 | False |
| LT_OFI_0240 | Order Flow | -1.458 | -3.136 | False |