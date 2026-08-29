
from pathlib import Path
from src.phase1_research import run_phase1
from src.phase1_report import build_phase1_html
if __name__=="__main__":
    root=Path(__file__).resolve().parent
    leaderboard,summary=run_phase1(root)
    build_phase1_html(root,leaderboard,summary)
    print("\nPHASE 1 COMPLETE\nOpen locally: docs/index.html\nTest set remains locked.")
