from __future__ import annotations

import argparse
from pathlib import Path

from src.phase2_low_turnover import run_phase2


def main():
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Run BTCUSDT Phase 2 low-turnover Train/Validation research."
    )
    parser.add_argument(
        "--config", type=Path,
        default=project_root / "configs" / "phase2_low_turnover.json",
    )
    parser.add_argument(
        "--data-path", type=Path,
        default=project_root / "data" / "processed" / "btc_core_1m_2020_2025.parquet",
    )
    parser.add_argument("--output-root", type=Path, default=project_root)
    args = parser.parse_args()

    if not args.data_path.exists():
        raise FileNotFoundError(
            f"Processed dataset not found: {args.data_path}\n"
            "Run RUN_PHASE1_CORE.ps1 first, or pass --data-path."
        )
    run_phase2(args.config.resolve(), args.data_path.resolve(), args.output_root.resolve())


if __name__ == "__main__":
    main()
