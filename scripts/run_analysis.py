from pathlib import Path
import json, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bazaarban.analytics import load_sales, analyze_sales

if __name__ == "__main__":
    csv_path = ROOT / "data/demo/sales_synthetic.csv"
    if not csv_path.exists():
        from bazaarban.generator import write_demo_data
        write_demo_data(ROOT)
    frame = load_sales(csv_path)
    summary = analyze_sales(frame)
    target = ROOT / "reports/generated_summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rows={summary['quality']['row_count']} valid={summary['quality']['valid_rows']} invalid={summary['quality']['invalid_rows']}")
    print(f"positive_net_sales_irr={summary['kpis']['positive_net_sales_irr']:.0f} invoices={summary['kpis']['distinct_positive_invoices']}")
    print(f"saved={target}")
