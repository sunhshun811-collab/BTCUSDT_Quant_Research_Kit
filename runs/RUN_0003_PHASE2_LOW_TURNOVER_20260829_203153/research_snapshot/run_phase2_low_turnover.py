from pathlib import Path
from src.phase2_low_turnover import run_phase2

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    run_phase2(
        root / 'configs' / 'phase2_low_turnover.json',
        root / 'data' / 'processed' / 'btc_core_1m_2020_2025.parquet',
        root,
    )
