"""Download, run, reconcile and report the official UCI Online Retail dataset."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, tempfile, time, urllib.request, zipfile
from pathlib import Path
import pandas as pd
from bazaarban.analytics import load_sales, analyze_sales
from bazaarban.uci_benchmark import adapt_uci_online_retail

DATASET_PAGE = "https://archive.ics.uci.edu/dataset/352/online+retail"
DOWNLOAD_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
EXPECTED_ROWS = 541_909
CITATION = "Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def fetch_workbook(folder: Path) -> tuple[Path, str]:
    archive_path = folder / "online-retail-uci.zip"
    request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent":"Bazaarban-UCI-benchmark/1.0"})
    last_error = None
    for attempt in range(1,4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response, archive_path.open("wb") as out:
                shutil.copyfileobj(response, out, length=1024*1024)
            break
        except Exception as exc:
            last_error = exc
            archive_path.unlink(missing_ok=True)
            if attempt == 3:
                raise RuntimeError(f"Could not download the official UCI archive: {last_error}") from last_error
            time.sleep(attempt)
    if not zipfile.is_zipfile(archive_path):
        raise ValueError("The UCI download is not a valid ZIP archive.")
    with zipfile.ZipFile(archive_path) as archive:
        members = [m for m in archive.infolist() if Path(m.filename).name.casefold() == "online retail.xlsx"]
        if len(members) != 1 or members[0].is_dir():
            raise ValueError(f"Expected exactly one Online Retail.xlsx; got {[m.filename for m in members[:10]]}")
        workbook = folder / "Online Retail.xlsx"
        with archive.open(members[0]) as source, workbook.open("wb") as dest:
            shutil.copyfileobj(source, dest, length=1024*1024)
    return workbook, sha256(workbook)

def sql_reconciliation(project_root: Path, adapted: pd.DataFrame, expected: dict) -> dict:
    db = sqlite3.connect(":memory:")
    try:
        db.executescript((project_root / "sql/schema.sql").read_text(encoding="utf-8"))
        fields = ["sale_date","invoice_id","store_id","store_name","product_code","product_name","category","customer_id","quantity","unit_price","discount"]
        values = []
        for row in adapted[fields].itertuples(index=False, name=None):
            values.append(tuple(None if pd.isna(v) else (float(v) if hasattr(v,"__float__") and not isinstance(v,str) else v) for v in row))
        db.executemany(
            "INSERT INTO sales_lines (sale_date,invoice_id,store_id,store_name,product_code,product_name,category,customer_id,quantity,unit_price,discount) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            values
        )
        sql_text = (project_root / "sql/analytics.sql").read_text(encoding="utf-8")
        statements = [s.strip() for s in sql_text.split(";") if "SELECT" in s.upper()]
        if len(statements) < 2:
            raise ValueError("Expected aggregate and repeat-customer queries in sql/analytics.sql")
        first = db.execute(statements[0]).fetchone()
        sql_result = {
            "gross_sales_gbp": float(first[0] or 0),
            "discount_total_gbp": float(first[1] or 0),
            "positive_net_sales_gbp": float(first[2] or 0),
            "signed_recorded_value_gbp": float(first[3] or 0),
            "distinct_positive_invoices": int(first[4] or 0),
        }
        kpi = expected["kpis"]
        expected_result = {
            "gross_sales_gbp": float(kpi["gross_sales_gbp"]),
            "discount_total_gbp": float(kpi["discount_total_gbp"]),
            "positive_net_sales_gbp": float(kpi["positive_net_sales_gbp"]),
            "signed_recorded_value_gbp": float(kpi["signed_recorded_value_gbp"]),
            "distinct_positive_invoices": int(kpi["distinct_positive_invoices"]),
        }
        for key, val in expected_result.items():
            if key == "distinct_positive_invoices":
                if sql_result[key] != val:
                    raise AssertionError(f"SQLite vs Pandas mismatch for {key}: {sql_result[key]} != {val}")
            elif abs(sql_result[key] - val) > max(0.02, abs(val)*1e-9):
                raise AssertionError(f"SQLite vs Pandas mismatch for {key}: {sql_result[key]} != {val}")
        second = db.execute(statements[1]).fetchone()
        sql_repeat = {"repeat_customers": int(second[0] or 0), "identified_customers": int(second[1] or 0)}
        if sql_repeat != {"repeat_customers":int(kpi["repeat_customers"]),"identified_customers":int(kpi["identified_customers"])}:
            raise AssertionError(f"SQLite vs Pandas customer mismatch: {sql_repeat}")
        return {"status":"passed","sqlite_aggregate":sql_result,"sqlite_customer_counts":sql_repeat,"compared_with_pandas":"5 monetary/invoice metrics + 2 repeat-customer counts"}
    finally:
        db.close()

def run(output: Path) -> dict:
    project_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="bazaarban_uci_") as temp:
        folder = Path(temp)
        workbook, digest = fetch_workbook(folder)
        source = pd.read_excel(workbook, sheet_name=0, dtype={"InvoiceNo":"string","Invoice":"string","StockCode":"string","CustomerID":"string","Customer ID":"string"})
        if len(source) != EXPECTED_ROWS:
            raise AssertionError(f"UCI row-count changed: expected {EXPECTED_ROWS:,}, got {len(source):,}; review source version before publication.")
        adapted = adapt_uci_online_retail(source)
        adapted_path = folder / "adapted.csv"
        adapted.to_csv(adapted_path, index=False)
        lines = load_sales(adapted_path)
        report = analyze_sales(
            lines, currency_code="GBP",
            dataset_classification="REAL PUBLIC SOURCE DATA — UCI Online Retail (no local customer data)"
        )
        raw_dates = pd.to_datetime(source["InvoiceDate"], errors="coerce", format="mixed")
        quality = report["quality"]
        kpi = report["kpis"]
        monthly_signed = sum(x["signed_recorded_value_gbp"] for x in report["monthly_trend"])
        product_gross = sum(x["gross_sales_gbp"] for x in report["top_products"])
        # top_products is intentionally top ten only, so only compare full-product totals below through direct source arithmetic.
        direct_eligible = (
            pd.to_numeric(adapted["quantity"], errors="coerce").gt(0) &
            pd.to_numeric(adapted["unit_price"], errors="coerce").gt(0) &
            ~adapted["invoice_id"].astype("string").str.strip().str.upper().str.startswith("C", na=False) &
            pd.to_datetime(adapted["sale_date"], errors="coerce").notna()
        )
        direct_gross = float((adapted.loc[direct_eligible,"quantity"] * adapted.loc[direct_eligible,"unit_price"]).sum())
        if abs(direct_gross - kpi["gross_sales_gbp"]) > max(0.02, abs(direct_gross)*1e-9):
            raise AssertionError(f"Independent source-to-KPI reconciliation failed: {direct_gross} != {kpi['gross_sales_gbp']}")
        if abs(monthly_signed - kpi["signed_recorded_value_gbp"]) > max(0.02, abs(kpi["signed_recorded_value_gbp"])*1e-9):
            raise AssertionError("Monthly signed values do not reconcile to total signed value.")
        if int(quality["financially_computable_rows"]) > len(source):
            raise AssertionError("Financially computable row count exceeds source row count.")
        sqlite_result = sql_reconciliation(project_root, adapted, report)
        result = {
            "dataset": "UCI Online Retail",
            "dataset_url": DATASET_PAGE,
            "dataset_doi": "https://doi.org/10.24432/C5BW33",
            "citation": CITATION,
            "license": "CC BY 4.0",
            "workbook_sha256": digest,
            "source_row_count": len(source),
            "source_column_names": [str(c) for c in source.columns],
            "source_date_min": str(raw_dates.min()),
            "source_date_max": str(raw_dates.max()),
            "currency_code": "GBP",
            "adapter_limitations": [
                "UCI is one online retailer and has no store/branch field; a single explicitly synthetic entity label is used, so multi-store ranking is not validated.",
                "The source has no discount or product-category field; discount is set to zero only for adapter arithmetic, and category is labelled unknown. These are not source facts.",
                "Missing product descriptions are flagged by quality rules but no longer cause otherwise computable transaction amounts to be omitted.",
                "Sales values are GBP recorded line amounts, not profit, cash collection, or verified accounting revenue."
            ],
            "quality": quality,
            "kpis": kpi,
            "checks": {
                "expected_source_row_count": EXPECTED_ROWS,
                "source_row_count_matches_official_metadata": len(source) == EXPECTED_ROWS,
                "python_direct_gross_sales_reconciles": abs(direct_gross - kpi["gross_sales_gbp"]) <= max(0.02,abs(direct_gross)*1e-9),
                "monthly_signed_value_reconciles": abs(monthly_signed - kpi["signed_recorded_value_gbp"]) <= max(0.02,abs(kpi["signed_recorded_value_gbp"])*1e-9),
                "sqlite_and_pandas_reconcile": sqlite_result["status"] == "passed",
                "all_product_groups_reported_for_rankings": len(report["top_products"]) <= 10,
                "source_rows_preserved_by_adapter": len(adapted) == len(source),
            },
            "sqlite_reconciliation": sqlite_result,
            "top_10_products_by_positive_sales": report["top_products"],
            "monthly_trend_first_last": [report["monthly_trend"][0], report["monthly_trend"][-1]] if report["monthly_trend"] else [],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if not all(result["checks"].values()):
            raise AssertionError("At least one benchmark validation check failed. Report was saved before failing.")
        return result

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("reports/uci_online_retail_benchmark.json"))
    args=parser.parse_args()
    run(args.output if args.output.is_absolute() else Path(__file__).resolve().parents[1] / args.output)
