
from __future__ import annotations
from pathlib import Path
import json
import shutil


LATEST_FILES = [
    "research_state.json",
    "manifest.json",
    "research_summary.md",
    "alpha_leaderboard.csv",
    "data_quality.json",
    "summary.json",
]


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists() or not src.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def mirror_repository_api(project_root: Path) -> dict:
    """
    Mirror compact GitHub research artifacts into docs/api so GitHub Pages exposes
    stable, directly fetchable machine-readable URLs.
    Raw market data is never mirrored.
    """
    docs_api = project_root / "docs" / "api"
    latest_src = project_root / "latest"
    runs_src = project_root / "runs"

    docs_api.mkdir(parents=True, exist_ok=True)

    # Stable latest mirror.
    latest_dst = docs_api / "latest"
    if latest_dst.exists():
        shutil.rmtree(latest_dst)
    latest_dst.mkdir(parents=True, exist_ok=True)

    copied_latest = []
    for name in LATEST_FILES:
        if copy_if_exists(latest_src / name, latest_dst / name):
            copied_latest.append(name)

    # Stable run catalog.
    copy_if_exists(runs_src / "index.json", docs_api / "runs" / "index.json")

    # Mirror compact artifacts for every immutable run.
    mirrored_runs = []
    if runs_src.exists():
        for rd in sorted(runs_src.glob("RUN_*")):
            if not rd.is_dir():
                continue
            out = docs_api / "runs" / rd.name
            for src_rel, dst_name in [
                ("manifest.json", "manifest.json"),
                ("research_summary.md", "research_summary.md"),
                ("results/alpha_leaderboard.csv", "alpha_leaderboard.csv"),
                ("results/summary.json", "summary.json"),
                ("results/data_quality.json", "data_quality.json"),
            ]:
                copy_if_exists(rd / src_rel, out / dst_name)
            mirrored_runs.append(rd.name)

    state = {}
    state_path = latest_src / "research_state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}

    public_index = {
        "schema_version": 1,
        "purpose": "Machine-readable mirror of compact BTCUSDT research artifacts.",
        "latest_run_id": state.get("latest_run_id"),
        "latest": {
            "research_state": "api/latest/research_state.json",
            "manifest": "api/latest/manifest.json",
            "summary": "api/latest/research_summary.md",
            "leaderboard": "api/latest/alpha_leaderboard.csv",
            "data_quality": "api/latest/data_quality.json",
        },
        "runs_index": "api/runs/index.json",
        "mirrored_run_count": len(mirrored_runs),
        "raw_market_data_published": False,
    }
    (docs_api / "index.json").write_text(
        json.dumps(public_index, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("GitHub Pages machine-readable mirror updated:")
    print("  docs/api/index.json")
    print("  docs/api/latest/")
    print("  docs/api/runs/index.json")
    print(f"  mirrored runs: {len(mirrored_runs)}")

    return public_index


if __name__ == "__main__":
    mirror_repository_api(Path(__file__).resolve().parents[1])
