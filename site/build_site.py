
from __future__ import annotations
from pathlib import Path
import argparse, csv, json, shutil

REQUIRED = [
    "alpha_leaderboard.csv",
    "cost_sensitivity.csv",
    "yearly_metrics.csv",
    "summary.json",
]

def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def csv_records(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def copy_if(src: Path, dst: Path):
    if not src.exists() or not src.is_file():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def main(repo: Path, out: Path):
    latest = repo / "official" / "latest"
    missing = [name for name in REQUIRED if not (latest / name).exists()]
    if missing:
        raise SystemExit("Missing official files: " + ", ".join(missing))

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    payload = {
        "officialPolicy": "PHASE2_ONLY",
        "summary": read_json(latest / "summary.json", {}),
        "state": read_json(repo / "official" / "state.json", {}),
        "manifest": read_json(latest / "manifest.json", {}),
        "quality": read_json(latest / "data_quality.json", {}),
        "config": read_json(repo / "research" / "configs" / "phase2_low_turnover.json", {}),
        "leaderboard": csv_records(latest / "alpha_leaderboard.csv"),
        "costSensitivity": csv_records(latest / "cost_sensitivity.csv"),
        "yearly": csv_records(latest / "yearly_metrics.csv"),
        "runs": read_json(repo / "runs" / "index.json", {"runs": []}).get("runs", []),
        "repoUrl": "https://github.com/sunhshun811-collab/BTCUSDT_Quant_Research_Kit",
    }

    shutil.copy2(repo / "site" / "template.html", out / "index.html")
    shutil.copytree(repo / "site" / "assets", out / "assets")
    (out / "site-data.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    dl = out / "data" / "latest"
    dl.mkdir(parents=True, exist_ok=True)
    for p in latest.iterdir():
        if p.is_file() and p.suffix.lower() in {".csv", ".json", ".md"}:
            shutil.copy2(p, dl / p.name)
    cfg = repo / "research" / "configs" / "phase2_low_turnover.json"
    copy_if(cfg, dl / "phase2_low_turnover_config.json")

    api = out / "api"
    api.mkdir(parents=True)
    (api / "index.json").write_text(json.dumps({
        "schema_version": 1,
        "official_result_policy": "PHASE2_ONLY",
        "phase": "PHASE2_LOW_TURNOVER",
        "home": "../",
        "downloads": {
            "leaderboard": "../data/latest/alpha_leaderboard.csv",
            "cost_sensitivity": "../data/latest/cost_sensitivity.csv",
            "yearly_metrics": "../data/latest/yearly_metrics.csv",
            "summary": "../data/latest/summary.json",
            "manifest": "../data/latest/manifest.json",
            "data_quality": "../data/latest/data_quality.json",
            "config": "../data/latest/phase2_low_turnover_config.json",
        }
    }, indent=2), encoding="utf-8")

    print("Built site:", out)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--output-dir", default="_site")
    a = ap.parse_args()
    main(Path(a.repo_root).resolve(), Path(a.output_dir).resolve())
