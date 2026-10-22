from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bazaarban.generator import write_demo_data

if __name__ == "__main__":
    print(write_demo_data(Path(__file__).resolve().parents[1]))
