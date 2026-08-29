
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import argparse, csv, hashlib, json, shutil, zipfile

EXCLUDE_SRC = {
    "phase1_report.py",
    "phase2_report.py",
    "report_builder.py",
    "github_pages_api_mirror.py",
    "research_archive.py",
    "research_package.py",
    "site_dashboard.py",
    "promote_phase2_only.py",
    "research_archive_generic.py",
    "publish_latest_report.py",
}
ROOT_RESEARCH_FILES = [
    "requirements.txt",
    "download_phase1_data.py",
    "build_phase1_dataset.py",
    "run_phase1_research.py",
    "run_phase2_low_turnover.py",
    "RUN_PHASE1_CORE.ps1",
    "RUN_PHASE2_LOW_TURNOVER.ps1",
    "RUN_RESEARCH.ps1",
]
RESULT_FILES = [
    "alpha_leaderboard.csv",
    "cost_sensitivity.csv",
    "yearly_metrics.csv",
    "summary.json",
]

def sha_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def tree_hash(root: Path) -> str:
    h=hashlib.sha256()
    if not root.exists():
        return h.hexdigest()
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(sha_file(p).encode())
    return h.hexdigest()

def reset_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True,exist_ok=True)

def copy_file(src: Path,dst: Path):
    if not src.exists() or not src.is_file():
        return False
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
    return True

def read_json(path: Path,default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default

def read_leaderboard(path: Path):
    if not path.exists():
        return []
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def as_bool(v):
    return v is True or str(v).lower() in {"1","true","yes"}

def as_float(v,default=float("-inf")):
    try:return float(v)
    except Exception:return default

def copy_research_code(research_root:Path,repo_root:Path):
    dst=repo_root/"research"
    reset_dir(dst)

    src_dir=research_root/"src"
    if src_dir.exists():
        for p in sorted(src_dir.glob("*.py")):
            if p.name in EXCLUDE_SRC:
                continue
            copy_file(p,dst/"src"/p.name)

    for dirname in ["configs","alphas"]:
        s=research_root/dirname
        if s.exists():
            for p in sorted(s.rglob("*")):
                if p.is_file():
                    copy_file(p,dst/dirname/p.relative_to(s))

    for name in ROOT_RESEARCH_FILES:
        copy_file(research_root/name,dst/name)

    # Research-only documentation, if present.
    for name in ["README.md","V3_PHASE1_README.md"]:
        copy_file(research_root/name,dst/name)

def copy_official_results(research_root:Path,repo_root:Path):
    src=research_root/"results"/"phase2_low_turnover"
    if not src.exists():
        raise FileNotFoundError(f"Official Phase2 results not found: {src}")
    for name in RESULT_FILES:
        if not (src/name).exists():
            raise FileNotFoundError(f"Missing official Phase2 result: {src/name}")

    latest=repo_root/"official"/"latest"
    reset_dir(latest)
    for name in RESULT_FILES:
        copy_file(src/name,latest/name)

    dq=research_root/"data"/"processed"/"data_quality.json"
    copy_file(dq,latest/"data_quality.json")
    cfg=research_root/"configs"/"phase2_low_turnover.json"
    copy_file(cfg,latest/"phase2_low_turnover_config.json")
    return latest

def make_manifest(repo_root:Path,latest:Path):
    summary=read_json(latest/"summary.json",{})
    lb=read_leaderboard(latest/"alpha_leaderboard.csv")
    candidate_count=sum(as_bool(r.get("phase2_candidate")) for r in lb)
    content_h=hashlib.sha256()
    for name in RESULT_FILES:
        content_h.update(name.encode())
        content_h.update(sha_file(latest/name).encode())
    content_hash=content_h.hexdigest()

    manifest={
        "schema_version":4,
        "official_result":True,
        "official_result_policy":"PHASE2_ONLY",
        "phase":"PHASE2_LOW_TURNOVER",
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "content_hash":content_hash,
        "research_code_hash":tree_hash(repo_root/"research"),
        "test_locked":bool(summary.get("test_locked",True)),
        "test_start":summary.get("test_start"),
        "visible_start":summary.get("visible_start"),
        "visible_end":summary.get("visible_end"),
        "rows_visible":summary.get("rows_visible"),
        "alphas_researched":int(summary.get("alphas_researched",len(lb))),
        "candidate_count":candidate_count,
        "files":{p.name:sha_file(p) for p in latest.iterdir() if p.is_file()},
    }
    (latest/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    return manifest,lb

def append_run_if_changed(repo_root:Path,manifest:dict,lb:list,force=False):
    official=repo_root/"official"
    state_path=official/"state.json"
    old=read_json(state_path,{})
    changed=force or old.get("content_hash")!=manifest["content_hash"]

    runs_dir=repo_root/"runs"
    runs_dir.mkdir(parents=True,exist_ok=True)
    index_path=runs_dir/"index.json"
    idx=read_json(index_path,{"schema_version":4,"official_result_policy":"PHASE2_ONLY","runs":[]})
    if not isinstance(idx.get("runs"),list):
        idx["runs"]=[]

    run_id=old.get("latest_run_id")
    if changed:
        n=max([int(r.get("run_number",0)) for r in idx["runs"]]+[0])+1
        stamp=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_id=f"RUN_{n:04d}_PHASE2_LOW_TURNOVER_{stamp}"
        rd=runs_dir/run_id
        rd.mkdir(parents=True,exist_ok=False)

        latest=repo_root/"official"/"latest"
        for p in latest.iterdir():
            if p.is_file():
                copy_file(p,rd/"results"/p.name)
        # Compact exact research snapshot.
        shutil.copytree(repo_root/"research",rd/"research_snapshot")

        top=sorted(lb,key=lambda r:as_float(r.get("val_net_sharpe_daily")),reverse=True)[:15]
        lines=[
            f"# {run_id}","",
            "- Official policy: `PHASE2_ONLY`",
            f"- Created UTC: `{manifest['created_at_utc']}`",
            f"- Test locked: `{manifest['test_locked']}`",
            f"- Alphas: `{manifest['alphas_researched']}`",
            f"- Candidates: `{manifest['candidate_count']}`","",
            "## Top validation results","",
            "| Alpha | Family | Train Sharpe | Validation Sharpe | Candidate |",
            "|---|---|---:|---:|---|",
        ]
        for r in top:
            lines.append(
                f"| {r.get('alpha_id','')} | {r.get('family','')} | "
                f"{r.get('train_net_sharpe_daily','')} | {r.get('val_net_sharpe_daily','')} | "
                f"{as_bool(r.get('phase2_candidate'))} |"
            )
        (rd/"research_summary.md").write_text("\n".join(lines),encoding="utf-8")
        run_manifest={**manifest,"run_id":run_id,"run_number":n}
        (rd/"manifest.json").write_text(json.dumps(run_manifest,indent=2,ensure_ascii=False),encoding="utf-8")

        idx["schema_version"]=4
        idx["official_result_policy"]="PHASE2_ONLY"
        idx["runs"].append({
            "run_id":run_id,"run_number":n,"phase":"PHASE2_LOW_TURNOVER",
            "created_at_utc":manifest["created_at_utc"],
            "alphas_researched":manifest["alphas_researched"],
            "candidate_count":manifest["candidate_count"],
            "test_locked":manifest["test_locked"],
            "content_hash":manifest["content_hash"],
        })
        index_path.write_text(json.dumps(idx,indent=2,ensure_ascii=False),encoding="utf-8")

    state={
        "schema_version":4,
        "official_result_policy":"PHASE2_ONLY",
        "phase":"PHASE2_LOW_TURNOVER",
        "official_result":True,
        "latest_run_id":run_id,
        "content_hash":manifest["content_hash"],
        "research_code_hash":manifest["research_code_hash"],
        "updated_at_utc":datetime.now(timezone.utc).isoformat(),
        "test_locked":manifest["test_locked"],
        "alphas_researched":manifest["alphas_researched"],
        "candidate_count":manifest["candidate_count"],
    }
    official.mkdir(parents=True,exist_ok=True)
    state_path.write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding="utf-8")
    return changed,run_id

def build_handoff(repo_root:Path,output:Path):
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_suffix(output.suffix+".tmp")
    if tmp.exists():tmp.unlink()
    allowed=[repo_root/"research",repo_root/"official"/"latest"]
    state=read_json(repo_root/"official"/"state.json",{})
    run_id=state.get("latest_run_id")
    if run_id:
        allowed += [repo_root/"runs"/run_id/"manifest.json",repo_root/"runs"/run_id/"research_summary.md"]
    allowed += [repo_root/"runs"/"index.json",repo_root/"official"/"state.json"]

    manifest={"schema_version":4,"official_result_policy":"PHASE2_ONLY","latest_run_id":run_id,"raw_market_data_included":False,"visualization_code_included":False,"files":[]}
    with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for item in allowed:
            if item.is_dir():
                for p in sorted(x for x in item.rglob("*") if x.is_file()):
                    rel=p.relative_to(repo_root).as_posix()
                    z.write(p,rel)
                    manifest["files"].append(rel)
            elif item.exists():
                rel=item.relative_to(repo_root).as_posix()
                z.write(item,rel)
                manifest["files"].append(rel)
        z.writestr("PACKAGE_MANIFEST.json",json.dumps(manifest,indent=2,ensure_ascii=False))
        z.writestr("READ_ME_FIRST.txt","Official Phase2 handoff. Contains research code and compact results only. No raw market data and no visualization code. Upload directly to ChatGPT.\n")
    if output.exists():output.unlink()
    tmp.replace(output)
    return output

def main(repo_root:Path,research_root:Path,package_output:Path|None,force_run=False):
    copy_research_code(research_root,repo_root)
    latest=copy_official_results(research_root,repo_root)
    manifest,lb=make_manifest(repo_root,latest)
    changed,run_id=append_run_if_changed(repo_root,manifest,lb,force=force_run)
    if package_output:
        build_handoff(repo_root,package_output)
    print("Official Phase2 synced.")
    print("New official run:",changed)
    print("Run ID:",run_id)
    print("Research code hash:",manifest["research_code_hash"])
    print("Result content hash:",manifest["content_hash"])

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",required=True)
    ap.add_argument("--research-root",required=True)
    ap.add_argument("--package-output")
    ap.add_argument("--force-run",action="store_true")
    a=ap.parse_args()
    main(Path(a.repo_root).resolve(),Path(a.research_root).resolve(),Path(a.package_output).resolve() if a.package_output else None,a.force_run)
