"""تولید دادهٔ مصنوعی ثابت برای بازتولید تحلیل و تست."""
from __future__ import annotations
from pathlib import Path
import json, random, hashlib, datetime
import pandas as pd

STORES = [("S-01", "فروشگاه بهار"), ("S-02", "سوپرمارکت آفتاب"), ("S-03", "فروشگاه مرکزی"), ("S-04", "فروشگاه سپید"), ("S-05", "فروشگاه ساحل")]
PRODUCTS = [
    ("P-01", "روغن مایع ۸۱۰ گرمی", "کالای اساسی", 690_000),
    ("P-02", "رب گوجه ۸۰۰ گرمی", "کنسرو و چاشنی", 350_000),
    ("P-03", "تن ماهی ۱۸۰ گرمی", "کنسرو و چاشنی", 330_000),
    ("P-04", "ماکارونی ۷۰۰ گرمی", "کالای اساسی", 210_000),
    ("P-05", "چای ۵۰۰ گرمی", "نوشیدنی", 1_250_000),
    ("P-06", "شیر یک لیتری", "لبنیات", 185_000),
    ("P-07", "پنیر ۴۰۰ گرمی", "لبنیات", 430_000),
    ("P-08", "مایع ظرف‌شویی", "شوینده", 290_000),
]

def generate_sales(seed: int = 20261021, invoices: int = 520) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    customers = [f"C-{i:04d}" for i in range(1, 181)]
    start = pd.Timestamp("2025-10-01")
    days_span = 385
    for i in range(invoices):
        store_id, store_name = rng.choice(STORES)
        day = start + pd.Timedelta(rng.randrange(days_span), unit="D")
        invoice_id = f"F-{100000+i}"
        customer = "" if rng.random() < 0.055 else rng.choice(customers)
        line_n = rng.choices([1,2,3,4], weights=[18,42,30,10])[0]
        for _ in range(line_n):
            code, pname, category, base = rng.choice(PRODUCTS)
            qty = rng.randint(1, 12)
            unit = max(10_000, int(base * rng.uniform(0.94, 1.12)))
            discount = int(qty * unit * rng.uniform(0, 0.075) // 1000 * 1000)
            rows.append({"sale_date": day.strftime("%Y-%m-%d"), "invoice_id": invoice_id, "store_id": store_id, "store_name": store_name, "product_code": code, "product_name": pname, "category": category, "customer_id": customer, "quantity": qty, "unit_price_irr": unit, "discount_irr": discount})
        if rng.random() < 0.04:
            code, pname, category, base = rng.choice(PRODUCTS)
            qty = -rng.randint(1, max(1, line_n//2))
            unit = max(10_000, int(base*rng.uniform(0.92,1.04)))
            rows.append({"sale_date": day.strftime("%Y-%m-%d"), "invoice_id": f"R-{invoice_id}", "store_id": store_id, "store_name": store_name, "product_code": code, "product_name": pname, "category": category, "customer_id": customer, "quantity": qty, "unit_price_irr": unit, "discount_irr": 0})
    columns = ["sale_date","invoice_id","store_id","store_name","product_code","product_name","category","customer_id","quantity","unit_price_irr","discount_irr"]
    frame = pd.DataFrame(rows, columns=columns)
    if len(frame) > 30:
        frame = pd.concat([frame, frame.iloc[[10, 22]].copy()], ignore_index=True)
        frame.loc[5, "unit_price_irr"] = -100
        frame.loc[7, "sale_date"] = "not-a-date"
        frame.loc[9, "invoice_id"] = ""
    return frame

def write_demo_data(project_root: str | Path, seed: int = 20261021, invoices: int = 520) -> dict:
    root = Path(project_root)
    out = root / "data" / "demo"
    out.mkdir(parents=True, exist_ok=True)
    frame = generate_sales(seed=seed, invoices=invoices)
    csv_path, json_path = out / "sales_synthetic.csv", out / "sales_synthetic.json"
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(frame.where(pd.notna(frame), None).to_dict(orient="records"), ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = root / "docs" / "dataset_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update({"generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "row_count": len(frame), "filename": csv_path.name, "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(), "generator_command": "python scripts/generate_demo_data.py", "seed": seed, "requested_invoice_count": invoices})
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"csv": str(csv_path), "json": str(json_path), "rows": len(frame), "seed": seed}
