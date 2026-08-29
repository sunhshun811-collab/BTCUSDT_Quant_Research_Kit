
from pathlib import Path
import argparse
from src.binance_public_data import download_archives

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["core","full"], default="core")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    download_archives(Path(__file__).resolve().parent, args.mode, args.workers)
