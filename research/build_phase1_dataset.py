
from pathlib import Path
from src.phase1_data_builder import build_core_dataset
if __name__ == "__main__":
    build_core_dataset(Path(__file__).resolve().parent)
