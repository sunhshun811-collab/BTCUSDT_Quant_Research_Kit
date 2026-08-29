
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import requests

BASE = "https://data.binance.vision"

@dataclass(frozen=True)
class ArchiveSpec:
    key: str
    market_path: str
    data_type: str
    symbol: str
    interval: str | None = None

    def monthly_url(self, year: int, month: int) -> str:
        ym = f"{year:04d}-{month:02d}"
        if self.interval:
            return (
                f"{BASE}/data/{self.market_path}/monthly/{self.data_type}/"
                f"{self.symbol}/{self.interval}/{self.symbol}-{self.interval}-{ym}.zip"
            )
        return (
            f"{BASE}/data/{self.market_path}/monthly/{self.data_type}/"
            f"{self.symbol}/{self.symbol}-{self.data_type}-{ym}.zip"
        )

    def local_path(self, root: Path, year: int, month: int) -> Path:
        ym = f"{year:04d}-{month:02d}"
        name = (
            f"{self.symbol}-{self.interval}-{ym}.zip"
            if self.interval else
            f"{self.symbol}-{self.data_type}-{ym}.zip"
        )
        return root / self.key / name

CORE_SPECS = [
    ArchiveSpec("futures_btcusdt_1m", "futures/um", "klines", "BTCUSDT", "1m"),
    ArchiveSpec("spot_btcusdt_1m", "spot", "klines", "BTCUSDT", "1m"),
    ArchiveSpec("spot_ethusdt_1m", "spot", "klines", "ETHUSDT", "1m"),
    ArchiveSpec("funding_btcusdt", "futures/um", "fundingRate", "BTCUSDT"),
]

FULL_EXTRA_SPECS = [
    ArchiveSpec("mark_btcusdt_1m", "futures/um", "markPriceKlines", "BTCUSDT", "1m"),
    ArchiveSpec("index_btcusdt_1m", "futures/um", "indexPriceKlines", "BTCUSDT", "1m"),
    ArchiveSpec("premium_btcusdt_1m", "futures/um", "premiumIndexKlines", "BTCUSDT", "1m"),
]

def iter_months():
    y, m = 2020, 1
    while (y, m) <= (2025, 12):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

def _download_one(item, raw_root: Path, timeout=90, retries=5):
    spec, year, month = item
    dest = spec.local_path(raw_root, year, month)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 100:
        return ("skip", spec.key, dest.name, dest.stat().st_size)

    url = spec.monthly_url(year, month)
    headers = {"User-Agent": "BTCUSDT-Quant-Research/1.0"}
    last_error = None
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=timeout, headers=headers) as r:
                if r.status_code == 404:
                    return ("missing", spec.key, dest.name, 0)
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                if tmp.stat().st_size <= 100:
                    raise RuntimeError("downloaded file too small")
                tmp.replace(dest)
                return ("ok", spec.key, dest.name, dest.stat().st_size)
        except Exception as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 12))
    return ("error", spec.key, dest.name, repr(last_error))

def download_archives(project_root: Path, mode="core", workers=8):
    raw_root = project_root / "data" / "raw" / "binance"
    specs = list(CORE_SPECS) + (FULL_EXTRA_SPECS if mode == "full" else [])
    items = [(spec, y, m) for spec in specs for y, m in iter_months()]
    print(f"Archive tasks: {len(items)} | mode={mode} | workers={workers}")
    counts = {"ok":0, "skip":0, "missing":0, "error":0}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fs = {ex.submit(_download_one, item, raw_root): item for item in items}
        for i, fut in enumerate(as_completed(fs), 1):
            status, key, name, extra = fut.result()
            counts[status] += 1
            if status in ("missing", "error"):
                print(f"[{i}/{len(items)}] {status.upper():7s} {key}/{name} {extra}")
            elif i % 10 == 0 or i == len(items):
                print(f"[{i}/{len(items)}] ok={counts['ok']} skip={counts['skip']} missing={counts['missing']} error={counts['error']}")
    print("Download summary:", counts)
    if counts["error"]:
        raise RuntimeError("Some downloads failed. Re-run the same command; completed files are skipped.")
    return counts
