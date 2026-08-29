
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, platform, shutil, subprocess, sys
import pandas as pd

RESULTS=[
 ("results/phase1/alpha_leaderboard.csv","alpha_leaderboard.csv"),
 ("results/phase1/summary.json","summary.json"),
 ("data/processed/data_quality.json","data_quality.json"),
]
SNAPSHOT=[
 "run_phase1_research.py","build_phase1_dataset.py","download_phase1_data.py",
 "RUN_PHASE1_CORE.ps1","PUBLISH_DASHBOARD.ps1","requirements.txt",
 ".gitignore",".gitattributes","configs/phase1_real_research.json",
 "src/phase1_research.py","src/phase1_report.py","src/phase1_data_builder.py",
 "src/binance_public_data.py"
]

def cmd(root,*args):
    try:
        p=subprocess.run(list(args),cwd=root,capture_output=True,text=True,check=False)
        return p.stdout.strip() if p.returncode==0 else None
    except Exception:
        return None

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def copy(src,dst):
    if not src.exists(): return False
    dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); return True

def next_no(root):
    n=0
    for p in (root/"runs").glob("RUN_*"):
        if p.is_dir():
            try:n=max(n,int(p.name.split("_",2)[1]))
            except:pass
    return n+1

def archive(root:Path, phase="REAL_PHASE1"):
    lbp=root/"results"/"phase1"/"alpha_leaderboard.csv"
    sump=root/"results"/"phase1"/"summary.json"
    if not lbp.exists(): raise FileNotFoundError(lbp)
    if not sump.exists(): raise FileNotFoundError(sump)
    lb=pd.read_csv(lbp); summary=json.loads(sump.read_text(encoding="utf-8"))
    n=next_no(root); stamp=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id=f"RUN_{n:04d}_{phase}_{stamp}"; rd=root/"runs"/run_id; rd.mkdir(parents=True)
    archived=[]
    for rel,name in RESULTS:
        if copy(root/rel,rd/"results"/name): archived.append(f"results/{name}")
    hashes={}
    for rel in SNAPSHOT:
        dst=rd/"code_snapshot"/rel
        if copy(root/rel,dst): hashes[rel]=sha(dst)
    quality={}
    qp=root/"data"/"processed"/"data_quality.json"
    if qp.exists():
        try: quality=json.loads(qp.read_text(encoding="utf-8"))
        except: pass
    manifest={
      "schema_version":1,"run_id":run_id,"run_number":n,"phase":phase,
      "created_at_utc":datetime.now(timezone.utc).isoformat(),
      "source_git_commit":cmd(root,"git","rev-parse","HEAD"),
      "source_git_branch":cmd(root,"git","branch","--show-current"),
      "working_tree_was_dirty_before_archive":bool(cmd(root,"git","status","--porcelain")),
      "python_version":sys.version,"platform":platform.platform(),
      "test_locked":bool(summary.get("test_locked",True)),
      "test_start":summary.get("test_start"),"visible_rows":summary.get("rows_visible"),
      "alphas_researched":summary.get("alphas_researched",len(lb)),
      "phase1_candidates":summary.get("phase1_candidates"),
      "families":summary.get("families",[]),
      "leaderboard_sha256":sha(lbp),"archived_files":archived,
      "code_snapshot_sha256":hashes,"data_quality":quality
    }
    (rd/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    top=lb.sort_values("val_net_sharpe_daily",ascending=False).head(10) if "val_net_sharpe_daily" in lb else lb.head(10)
    lines=[f"# {run_id}","",f"- Phase: `{phase}`",f"- Created UTC: `{manifest['created_at_utc']}`",
           f"- Test locked: `{manifest['test_locked']}`",f"- Alpha count: `{len(lb)}`","",
           "## Top validation results","",
           "| Alpha | Family | Train Sharpe | Validation Sharpe | Val IC 1m | Candidate |",
           "|---|---|---:|---:|---:|---|"]
    for _,r in top.iterrows():
        def f(v,d=3):
            try:return "" if pd.isna(v) else f"{float(v):.{d}f}"
            except:return str(v)
        lines.append(f"| {r.get('alpha_id','')} | {r.get('family','')} | {f(r.get('train_net_sharpe_daily'))} | {f(r.get('val_net_sharpe_daily'))} | {f(r.get('val_ic_1m'),4)} | {bool(r.get('phase1_candidate',False))} |")
    lines += ["","## Research integrity","","Raw/processed market data stay local. Results, code/config snapshots and reproducibility metadata are archived in GitHub."]
    (rd/"research_summary.md").write_text("\n".join(lines),encoding="utf-8")
    latest=root/"latest"
    if latest.exists(): shutil.rmtree(latest)
    latest.mkdir()
    for src,name in [(rd/"manifest.json","manifest.json"),(rd/"research_summary.md","research_summary.md"),
                     (rd/"results"/"alpha_leaderboard.csv","alpha_leaderboard.csv"),
                     (rd/"results"/"summary.json","summary.json"),
                     (rd/"results"/"data_quality.json","data_quality.json")]:
        copy(src,latest/name)
    state={"schema_version":1,"latest_run_id":run_id,"latest_run_path":f"runs/{run_id}",
           "phase":phase,"updated_at_utc":manifest["created_at_utc"],"test_locked":manifest["test_locked"],
           "alphas_researched":manifest["alphas_researched"],"phase1_candidates":manifest["phase1_candidates"],
           "source_git_commit":manifest["source_git_commit"],
           "stable_files":{"manifest":"latest/manifest.json","summary":"latest/research_summary.md",
                           "leaderboard":"latest/alpha_leaderboard.csv","data_quality":"latest/data_quality.json"}}
    (latest/"research_state.json").write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding="utf-8")
    ip=root/"runs"/"index.json"
    idx=json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else {"schema_version":1,"runs":[]}
    idx["runs"].append({"run_id":run_id,"run_number":n,"phase":phase,"created_at_utc":manifest["created_at_utc"],
                        "path":f"runs/{run_id}","alphas_researched":manifest["alphas_researched"],
                        "phase1_candidates":manifest["phase1_candidates"],"test_locked":manifest["test_locked"],
                        "source_git_commit":manifest["source_git_commit"]})
    ip.write_text(json.dumps(idx,indent=2,ensure_ascii=False),encoding="utf-8")
    print("Archived:",run_id); print("Latest:",latest); return rd

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--phase",default="REAL_PHASE1"); a=ap.parse_args()
    archive(Path(__file__).resolve().parents[1],a.phase)
