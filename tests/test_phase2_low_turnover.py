import unittest

import numpy as np
import pandas as pd

from src.phase2_low_turnover import build_position, daily_metrics


class Phase2LowTurnoverTests(unittest.TestCase):
    def test_position_uses_delayed_feature(self):
        index = pd.date_range("2024-01-01", periods=40, freq="1min", tz="UTC")
        feature = pd.Series(np.arange(40, dtype=float), index=index)
        position = build_position(
            feature=feature,
            normalization_lookback=5,
            clip_z=3.0,
            rebalance_minutes=1,
            smoothing_halflife=1,
            no_trade_band=0.0,
            position_step=0.1,
            position_cap=1.0,
        )
        self.assertEqual(float(position.iloc[4]), 0.0)
        self.assertGreater(float(position.iloc[6]), 0.0)

    def test_no_trade_band_reduces_updates(self):
        index = pd.date_range("2024-01-01", periods=300, freq="1min", tz="UTC")
        feature = pd.Series(np.sin(np.arange(300) / 30.0), index=index)
        loose = build_position(feature, 20, 3.0, 5, 10, 0.0, 0.1, 1.0)
        banded = build_position(feature, 20, 3.0, 5, 10, 0.2, 0.1, 1.0)
        self.assertLessEqual(int((banded.diff().abs() > 0).sum()), int((loose.diff().abs() > 0).sum()))

    def test_daily_metrics_are_finite(self):
        index = pd.date_range("2024-01-01", periods=3 * 1440, freq="1min", tz="UTC")
        returns = pd.Series(0.000001, index=index)
        position = pd.Series(0.5, index=index)
        metrics = daily_metrics(returns, position, returns)
        self.assertTrue(np.isfinite(metrics["net_return"]))
        self.assertEqual(metrics["trade_events"], 1)


if __name__ == "__main__":
    unittest.main()
