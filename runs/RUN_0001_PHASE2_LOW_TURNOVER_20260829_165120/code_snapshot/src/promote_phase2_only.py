
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess
import pandas as pd

PHASE = "PHASE2_LOW_TURNOVER"
RESULT_DIR = Path("results/phase2_low_turnover")
REPORT_FILE = Path("reports/phase2_low_turnover_dashboard.html")
MAX_BYTES = 20 * 1024 * 1024

def git(root: Path, *args: str) -> str | None:
    try:
        p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def cp(src: Path, dst: Path) -> bool:
    if not src.exists() or not src.is_file() or src.stat().st_size > MAX_BYTES:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True

def reset_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)

def promote(project_root: Path):
    result_dir = project_root / RESULT_DIR
    report = project_root / REPORT_FILE
    leaderboard = result_dir / "alpha_leaderboard.csv"
    summary_path = result_dir / "summary.json"

    if not leaderboard.exists():
        raise FileNotFoundError(
            f"Official Phase2 leaderboard not found: {leaderboard}"
        )
    if not report.exists():
        raise FileNotFoundError(
            f"Official Phase2 report not found: {report}"
        )

    lb = pd.read_csv(leaderboard)
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    # Remove deprecated Phase1 CURRENT artifacts.
    deprecated_paths = [
        project_root / "results" / "phase1",
        project_root / "reports" / "quant_research_dashboard.html",
    ]
    for p in deprecated_paths:
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()

    # Current research history becomes Phase2-only.
    # Old states remain recoverable from Git history, but disappear from working tree.
    runs = project_root / "runs"
    latest = project_root / "latest"
    reset_dir(runs)
    reset_dir(latest)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"RUN_0001_{PHASE}_{stamp}"
    run_dir = runs / run_id
    run_dir.mkdir(parents=True)

    # Archive every compact Phase2 result.
    archived_results = []
    for p in sorted(result_dir.rglob("*")):
        if p.is_file() and p.stat().st_size <= MAX_BYTES:
            rel = p.relative_to(result_dir)
            cp(p, run_dir / "results" / rel)
            archived_results.append(f"results/{rel.as_posix()}")

    cp(report, run_dir / "report.html")

    # Snapshot current research code/config.
    code_hashes = {}
    candidates = []
    candidates += sorted((project_root/"src").glob("*.py"))
    candidates += sorted(project_root.glob("*.py"))
    candidates += sorted(project_root.glob("*.ps1"))
    candidates += sorted((project_root/"configs").glob("*.json"))
    for p in candidates:
        if not p.is_file() or p.stat().st_size > MAX_BYTES:
            continue
        rel = p.relative_to(project_root)
        dst = run_dir / "code_snapshot" / rel
        cp(p, dst)
        code_hashes[rel.as_posix()] = sha(dst)

    candidate_col = "phase2_candidate" if "phase2_candidate" in lb.columns else None
    candidate_count = int(lb[candidate_col].fillna(False).astype(bool).sum()) if candidate_col else None

    manifest = {
        "schema_version": 3,
        "official_result": True,
        "official_result_policy": "PHASE2_ONLY",
        "run_id": run_id,
        "run_number": 1,
        "phase": PHASE,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_git_commit_before_promotion": git(project_root, "rev-parse", "HEAD"),
        "source_git_branch": git(project_root, "branch", "--show-current"),
        "test_locked": bool(summary.get("test_locked", True)),
        "test_start": summary.get("test_start"),
        "visible_rows": summary.get("rows_visible"),
        "alphas_researched": int(summary.get("alphas_researched", len(lb))),
        "candidate_count": candidate_count,
        "leaderboard_sha256": sha(leaderboard),
        "archived_results": archived_results,
        "code_snapshot_sha256": code_hashes,
        "deprecated_results_removed_from_working_tree": [
            "results/phase1",
            "reports/quant_research_dashboard.html",
            "previous latest/",
            "previous runs/"
        ],
        "note": "Older experiments remain recoverable through Git history but are not official current research results."
    }
    (run_dir/"manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Stable latest is Phase2 only.
    for p in sorted(result_dir.rglob("*")):
        if p.is_file() and p.stat().st_size <= MAX_BYTES:
            cp(p, latest / p.relative_to(result_dir))
    cp(report, latest/"report.html")
    cp(run_dir/"manifest.json", latest/"manifest.json")

    state = {
        "schema_version": 3,
        "official_result_policy": "PHASE2_ONLY",
        "latest_run_id": run_id,
        "latest_run_path": f"runs/{run_id}",
        "phase": PHASE,
        "official_result": True,
        "updated_at_utc": manifest["created_at_utc"],
        "test_locked": manifest["test_locked"],
        "alphas_researched": manifest["alphas_researched"],
        "candidate_count": candidate_count,
        "result_source": RESULT_DIR.as_posix(),
        "report_source": REPORT_FILE.as_posix(),
    }
    (latest/"research_state.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Human-readable summary.
    sort_col = "val_net_sharpe_daily" if "val_net_sharpe_daily" in lb.columns else None
    top = lb.sort_values(sort_col, ascending=False).head(20) if sort_col else lb.head(20)
    lines = [
        "# Official BTCUSDT Research Result",
        "",
        f"- Policy: **PHASE2 ONLY**",
        f"- Phase: `{PHASE}`",
        f"- Run: `{run_id}`",
        f"- Test locked: `{manifest['test_locked']}`",
        f"- Alpha count: `{len(lb)}`",
        "",
        "All previous Phase1 baseline outputs are deprecated and are not part of the current official result.",
        "They remain available only through Git history.",
        "",
    ]
    if sort_col:
        lines += [
            "## Top validation results",
            "",
            "| Alpha | Family | Train Sharpe | Validation Sharpe | Candidate |",
            "|---|---|---:|---:|---|",
        ]
        for _, r in top.iterrows():
            def f(v):
                try:
                    return "" if pd.isna(v) else f"{float(v):.3f}"
                except Exception:
                    return str(v)
            lines.append(
                f"| {r.get('alpha_id','')} | {r.get('family','')} | "
                f"{f(r.get('train_net_sharpe_daily'))} | "
                f"{f(r.get('val_net_sharpe_daily'))} | "
                f"{bool(r.get('phase2_candidate', False))} |"
            )
    (latest/"research_summary.md").write_text("\n".join(lines), encoding="utf-8")
    cp(latest/"research_summary.md", run_dir/"research_summary.md")

    # Only one current run in working tree.
    index = {
        "schema_version": 3,
        "official_result_policy": "PHASE2_ONLY",
        "runs": [{
            "run_id": run_id,
            "run_number": 1,
            "phase": PHASE,
            "official_result": True,
            "created_at_utc": manifest["created_at_utc"],
            "path": f"runs/{run_id}",
            "alphas_researched": manifest["alphas_researched"],
            "candidate_count": candidate_count,
            "test_locked": manifest["test_locked"],
        }]
    }
    (runs/"index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Website homepage = official Phase2 report.
    docs = project_root/"docs"
    docs.mkdir(parents=True, exist_ok=True)
    cp(report, docs/"index.html")
    (docs/"OFFICIAL_RESEARCH_STATE.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("PHASE2 PROMOTED AS THE ONLY OFFICIAL RESULT")
    print("Official run:", run_id)
    print("Website:", docs/"index.html")
    print("Deprecated Phase1 current artifacts removed.")

if __name__ == "__main__":
    promote(Path(__file__).resolve().parents[1])
