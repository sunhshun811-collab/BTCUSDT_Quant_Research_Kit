
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, subprocess, zipfile

MAX=20*1024*1024
EXCL={".git","data","__pycache__",".venv","venv"}
SUFFIX_EXCL={".parquet",".zip",".gz",".7z",".rar"}
DIRS=["latest","runs","results/phase2_low_turnover","reports","src","configs","alphas","docs"]
ROOT_SUFFIX={".py",".ps1",".md",".json",".txt",".yml",".yaml"}
ROOT_NAMES={"requirements.txt",".gitignore",".gitattributes","README.md"}

def git(root,*a):
    try:
        p=subprocess.run(["git",*a],cwd=root,capture_output=True,text=True)
        return p.stdout if p.returncode==0 else p.stderr
    except Exception as e:return str(e)

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def ok(p,root):
    if not p.is_file() or p.stat().st_size>MAX:return False
    rel=p.relative_to(root)
    if any(x in EXCL for x in rel.parts):return False
    if p.suffix.lower() in SUFFIX_EXCL:return False
    return True

def build(root,out):
    files={}
    for p in root.iterdir():
        if p.is_file() and (p.name in ROOT_NAMES or p.suffix.lower() in ROOT_SUFFIX) and ok(p,root):
            files[p.relative_to(root).as_posix()]=p
    for dname in DIRS:
        d=root/dname
        if d.exists():
            for p in d.rglob("*"):
                if ok(p,root):files[p.relative_to(root).as_posix()]=p
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(".zip.tmp")
    if tmp.exists():tmp.unlink()
    manifest={
      "schema_version":3,"official_result_policy":"PHASE2_ONLY",
      "created_at_utc":datetime.now(timezone.utc).isoformat(),
      "git_commit":git(root,"rev-parse","HEAD").strip(),
      "included_file_count":len(files),
      "codex_required":False,"raw_market_data_included":False,"files":[]
    }
    with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for rel,p in sorted(files.items()):
            arc=f"project/{rel}";z.write(p,arc)
            manifest["files"].append({"path":arc,"bytes":p.stat().st_size,"sha256":sha(p)})
        z.writestr("git/status.txt",git(root,"status","--short"))
        z.writestr("git/diff_unstaged.patch",git(root,"diff","--no-ext-diff"))
        z.writestr("git/log_last_20.txt",git(root,"log","-n","20","--date=iso","--pretty=format:%H%x09%ad%x09%s"))
        z.writestr("PACKAGE_MANIFEST.json",json.dumps(manifest,indent=2,ensure_ascii=False))
        z.writestr("READ_ME_FIRST.txt","Official policy: PHASE2_ONLY. Upload this ZIP to ChatGPT. Phase1 baseline is deprecated and intentionally excluded as a result.\n")
    if out.exists():out.unlink()
    tmp.replace(out)
    print("Created:",out)
    print("Files:",len(files),"Size MB:",round(out.stat().st_size/1024/1024,2))
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--project-root",required=True);a.add_argument("--output",required=True);x=a.parse_args()
    build(Path(x.project_root).resolve(),Path(x.output).resolve())
