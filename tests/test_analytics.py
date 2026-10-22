from datetime import date
import pandas as pd
import pytest
from bazaarban.analytics import analyze_sales, load_sales, quality_report
from bazaarban.calendar_fa import gregorian_to_jalali, format_jalali_date, sort_by_gregorian_date
from bazaarban.generator import generate_sales

def tiny_frame():
    return pd.DataFrame([
        {"sale_date":"2026-03-21","invoice_id":"F-1","store_id":"S-1","store_name":"فروشگاه یک","product_code":"P-1","product_name":"کالا الف","category":"خوراکی","customer_id":"C-1","quantity":2,"unit_price_irr":100,"discount_irr":10},
        {"sale_date":"2026-03-21","invoice_id":"F-1","store_id":"S-1","store_name":"فروشگاه یک","product_code":"P-2","product_name":"کالا ب","category":"خوراکی","customer_id":"C-1","quantity":1,"unit_price_irr":50,"discount_irr":0},
        {"sale_date":"2026-04-02","invoice_id":"F-2","store_id":"S-1","store_name":"فروشگاه یک","product_code":"P-1","product_name":"کالا الف","category":"خوراکی","customer_id":"C-1","quantity":1,"unit_price_irr":100,"discount_irr":0},
        {"sale_date":"2026-04-02","invoice_id":"R-F-2","store_id":"S-1","store_name":"فروشگاه یک","product_code":"P-1","product_name":"کالا الف","category":"خوراکی","customer_id":"C-1","quantity":-1,"unit_price_irr":100,"discount_irr":0},
    ])

def load_in_memory(frame):
    frame = frame.copy()
    frame["source_row_id"] = range(1, len(frame)+1)
    frame["sale_date_parsed"] = pd.to_datetime(frame["sale_date"], errors="coerce", format="%Y-%m-%d")
    for col in ["quantity","unit_price_irr","discount_irr"]:
        frame[col+"_parsed"] = pd.to_numeric(frame[col], errors="coerce")
    frame["line_gross_irr"] = frame["quantity_parsed"] * frame["unit_price_irr_parsed"]
    frame["line_recorded_value_irr"] = frame["line_gross_irr"] - frame["discount_irr_parsed"]
    frame["is_return_line"] = frame["quantity_parsed"] < 0
    return frame

def test_jalali_conversion_known_boundary_and_format():
    assert gregorian_to_jalali(date(2026, 3, 20)) == (1405, 1, 1)
    assert format_jalali_date("2026-03-20", persian_digits=False) == "1405/01/01"
    assert format_jalali_date("2026-03-20") == "۱۴۰۵/۰۱/۰۱"

def test_sorting_uses_stored_gregorian_iso_not_display_string():
    rows = [{"sale_date":"2026-10-01","display":"۱۴۰۵/۰۷/۰۹"},{"sale_date":"2026-03-21","display":"۱۴۰۵/۰۱/۰۱"}]
    assert [x["sale_date"] for x in sort_by_gregorian_date(rows)] == ["2026-03-21","2026-10-01"]

def test_invoice_denominator_counts_distinct_invoice_not_lines_and_return_is_separate():
    report = analyze_sales(load_in_memory(tiny_frame()))
    kpi = report["kpis"]
    assert kpi["gross_sales_irr"] == 350.0
    assert kpi["discount_total_irr"] == 10.0
    assert kpi["positive_net_sales_irr"] == 340.0
    assert kpi["distinct_positive_invoices"] == 2
    assert kpi["average_positive_invoice_value_irr"] == 170.0
    assert kpi["return_value_proxy_irr"] == 100.0
    assert kpi["signed_recorded_value_irr"] == 240.0
    assert kpi["repeat_customer_rate"] == 1.0

def test_bad_dates_and_negative_price_are_counted_invalid():
    frame = load_in_memory(tiny_frame())
    frame.loc[0,"sale_date_parsed"] = pd.NaT
    frame.loc[1,"unit_price_irr_parsed"] = -1
    audit = quality_report(frame)
    assert audit["invalid_rows"] == 2
    assert audit["invalid_row_rate"] == 0.5

def test_generator_is_deterministic_and_contains_explicit_demo_anomalies():
    a = generate_sales(seed=7, invoices=35)
    b = generate_sales(seed=7, invoices=35)
    pd.testing.assert_frame_equal(a, b)
    audit = quality_report(load_in_memory(a))
    assert audit["row_count"] > 35
    assert audit["invalid_rows"] >= 2
    assert audit["exact_duplicate_candidate_rows"] >= 1

def test_date_filter_uses_gregorian_storage():
    frame = load_in_memory(tiny_frame())
    report = analyze_sales(frame, start_date="2026-04-01")
    assert report["kpis"]["distinct_positive_invoices"] == 1
    assert report["kpis"]["return_line_count"] == 1

def test_sql_and_pandas_reconcile_on_same_fixture():
    import sqlite3
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = tiny_frame()
    frame = load_in_memory(source)
    report = analyze_sales(frame)
    conn = sqlite3.connect(":memory:")
    conn.executescript((root / "sql/schema.sql").read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT INTO sales_lines (sale_date,invoice_id,store_id,store_name,product_code,product_name,category,customer_id,quantity,unit_price,discount) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [tuple(row.get(src) for src in ["sale_date","invoice_id","store_id","store_name","product_code","product_name","category","customer_id","quantity","unit_price_irr","discount_irr"]) for row in source.to_dict(orient="records")]
    )
    sql = (root / "sql/analytics.sql").read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if "SELECT" in s.upper()]
    output = conn.execute(statements[0]).fetchone()
    kpi = report["kpis"]
    assert output[0] == kpi["gross_sales_irr"]
    assert output[1] == kpi["discount_total_irr"]
    assert output[2] == kpi["positive_net_sales_irr"]
    assert output[3] == kpi["signed_recorded_value_irr"]
    assert output[4] == kpi["distinct_positive_invoices"]
    conn.close()

def test_missing_product_name_remains_visible_but_does_not_drop_computable_sales():
    source = tiny_frame()
    source.loc[0,"product_name"] = ""
    prepared = load_in_memory(source)
    report = analyze_sales(prepared)
    assert report["quality"]["missing_product_name_rows"] == 1
    assert report["quality"]["invalid_rows"] == 1
    # First line still contributes 2 * 100 - 10 = 190 to financial metrics.
    assert report["kpis"]["positive_net_sales_irr"] == 340.0
    assert report["kpis"]["financially_computable_line_count"] == 4
    assert any(p["product_name"] == "بدون توضیح در منبع" for p in report["top_products"])

def test_cancelled_invoice_with_positive_quantity_is_not_positive_sales():
    source = pd.DataFrame([{
        "sale_date":"2026-01-02","invoice_id":"c123","store_id":"S-1","store_name":"فروشگاه یک",
        "product_code":"P-1","product_name":"کالا","category":"خوراکی","customer_id":"C-1",
        "quantity":2,"unit_price_irr":100,"discount_irr":0
    }])
    report = analyze_sales(load_in_memory(source))
    assert report["kpis"]["gross_sales_irr"] == 0.0
    assert report["kpis"]["distinct_positive_invoices"] == 0
    assert report["kpis"]["cancellation_positive_rows_excluded"] == 1

def test_generic_currency_schema_reports_the_source_currency_not_irr(tmp_path):
    frame = pd.DataFrame([{
        "sale_date":"2026-01-02","invoice_id":"100","store_id":"UCI","store_name":"One online retailer",
        "product_code":"A","product_name":"Item","category":"Unknown","customer_id":"1",
        "quantity":2,"unit_price":1.25,"discount":0.0
    }])
    path=tmp_path/"gbp.csv"; frame.to_csv(path,index=False)
    report=analyze_sales(load_sales(path),currency_code="GBP",dataset_classification="REAL PUBLIC SOURCE DATA")
    assert report["currency_code"] == "GBP"
    assert report["kpis"]["gross_sales_gbp"] == 2.5
    assert "gross_sales_irr" not in report["kpis"]
