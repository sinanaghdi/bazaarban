from pathlib import Path
import json
from .analytics import load_sales, analyze_sales
from .generator import write_demo_data

root = Path(__file__).resolve().parents[2]
data = root / "data/demo/sales_synthetic.csv"
if not data.exists():
    write_demo_data(root)
report = analyze_sales(load_sales(data))
out = root / "reports/generated_summary.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"output": str(out), "rows": report["quality"]["row_count"], "valid_rows": report["quality"]["valid_rows"]}, ensure_ascii=False, indent=2))
