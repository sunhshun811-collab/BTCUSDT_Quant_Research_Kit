
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import argparse, csv, hashlib, json, os, shutil, subprocess, zipfile

REQUIRED = ["alpha_leaderboard.csv","cost_sensitivity.csv","yearly_metrics.csv","summary.json"]

def read_json(path: Path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def csv_records(path: Path):
    if not path.exists(): return []
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def copy_if(src: Path,dst: Path):
    if not src.exists() or not src.is_file(): return
    dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)

def sha256(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def git_commit(repo: Path):
    if os.environ.get("GITHUB_SHA"): return os.environ["GITHUB_SHA"]
    try:
        p=subprocess.run(["git","rev-parse","HEAD"],cwd=repo,capture_output=True,text=True)
        if p.returncode==0:return p.stdout.strip()
    except Exception: pass
    return None

def package_files(repo: Path):
    state=read_json(repo/"official"/"state.json",{})
    run_id=state.get("latest_run_id")
    items=[repo/"research",repo/"official"/"latest",repo/"official"/"state.json",repo/"runs"/"index.json"]
    if run_id:
        items += [repo/"runs"/run_id/"manifest.json",repo/"runs"/run_id/"research_summary.md"]
    found={}
    for item in items:
        if item.is_dir():
            for p in item.rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts and p.suffix.lower() not in {".pyc",".zip",".parquet"}:
                    found[p.relative_to(repo).as_posix()]=p
        elif item.is_file():
            found[item.relative_to(repo).as_posix()]=item
    return [found[k] for k in sorted(found)],state

def build_analysis_package(repo: Path,out: Path):
    out.parent.mkdir(parents=True,exist_ok=True)
    files,state=package_files(repo); run_id=state.get("latest_run_id")
    tmp=out.with_suffix(out.suffix+".tmp")
    if tmp.exists():tmp.unlink()
    manifest={"schema_version":6,"purpose":"ChatGPT analysis handoff package","official_result_policy":"PHASE2_ONLY",
              "latest_run_id":run_id,"created_at_utc":datetime.now(timezone.utc).isoformat(),
              "github_commit":git_commit(repo),"raw_market_data_included":False,"visualization_code_included":False,
              "file_count":len(files),"files":[]}
    with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
            rel=p.relative_to(repo).as_posix();z.write(p,rel)
            manifest["files"].append({"path":rel,"bytes":p.stat().st_size,"sha256":sha256(p)})
        z.writestr("PACKAGE_MANIFEST.json",json.dumps(manifest,indent=2,ensure_ascii=False))
        z.writestr("README_FIRST.txt","这是最新 ChatGPT 分析包：研究代码 + 配置 + 官方 Phase2 结果 + 状态 + 最新 Run 摘要。无原始行情、无可视化代码。请直接上传给 ChatGPT。\\n")
    if out.exists():out.unlink()
    tmp.replace(out)
    return {"filename":out.name,"latest_run_id":run_id,"bytes":out.stat().st_size,
            "size_mb":round(out.stat().st_size/1024/1024,4),"sha256":sha256(out),
            "file_count":len(files),"created_at_utc":datetime.now(timezone.utc).isoformat()}

def main(repo: Path,out: Path):
    latest=repo/"official"/"latest"
    missing=[name for name in REQUIRED if not (latest/name).exists()]
    if missing:raise SystemExit("Missing official files: "+", ".join(missing))
    if out.exists():shutil.rmtree(out)
    out.mkdir(parents=True)

    downloads=out/"downloads"
    package_info=build_analysis_package(repo,downloads/"research_package_latest.zip")
    (downloads/"research_package_info.json").write_text(json.dumps(package_info,indent=2,ensure_ascii=False),encoding="utf-8")

    payload={"officialPolicy":"PHASE2_ONLY","summary":read_json(latest/"summary.json",{}),
             "state":read_json(repo/"official"/"state.json",{}),"manifest":read_json(latest/"manifest.json",{}),
             "quality":read_json(latest/"data_quality.json",{}),
             "config":read_json(repo/"research"/"configs"/"phase2_low_turnover.json",{}),
             "leaderboard":csv_records(latest/"alpha_leaderboard.csv"),
             "costSensitivity":csv_records(latest/"cost_sensitivity.csv"),
             "yearly":csv_records(latest/"yearly_metrics.csv"),
             "runs":read_json(repo/"runs"/"index.json",{"runs":[]}).get("runs",[]),
             "repoUrl":"https://github.com/sunhshun811-collab/BTCUSDT_Quant_Research_Kit",
             "packageInfo":package_info}

    shutil.copy2(repo/"site"/"template.html",out/"index.html")
    shutil.copytree(repo/"site"/"assets",out/"assets")
    (out/"site-data.json").write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")

    dl=out/"data"/"latest";dl.mkdir(parents=True,exist_ok=True)
    for p in latest.iterdir():
        if p.is_file() and p.suffix.lower() in {".csv",".json",".md"}:shutil.copy2(p,dl/p.name)
    copy_if(repo/"research"/"configs"/"phase2_low_turnover.json",dl/"phase2_low_turnover_config.json")

    api=out/"api";api.mkdir(parents=True)
    (api/"index.json").write_text(json.dumps({
        "schema_version":2,"official_result_policy":"PHASE2_ONLY","phase":"PHASE2_LOW_TURNOVER","home":"../",
        "analysis_package":"../downloads/research_package_latest.zip",
        "analysis_package_info":"../downloads/research_package_info.json",
        "downloads":{"leaderboard":"../data/latest/alpha_leaderboard.csv","cost_sensitivity":"../data/latest/cost_sensitivity.csv",
                     "yearly_metrics":"../data/latest/yearly_metrics.csv","summary":"../data/latest/summary.json",
                     "manifest":"../data/latest/manifest.json","data_quality":"../data/latest/data_quality.json",
                     "config":"../data/latest/phase2_low_turnover_config.json"}},indent=2,ensure_ascii=False),encoding="utf-8")
    print("Built site:",out)
    print("Analysis package:",downloads/"research_package_latest.zip")
    print("Analysis package size MB:",package_info["size_mb"])

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--repo-root",default=".");ap.add_argument("--output-dir",default="_site");a=ap.parse_args()
    main(Path(a.repo_root).resolve(),Path(a.output_dir).resolve())
