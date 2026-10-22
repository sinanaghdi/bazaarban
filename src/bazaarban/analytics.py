"""تحلیل فروش و کنترل کیفیت؛ خروجی‌ها صرفاً درباره داده‌های موجود هستند."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import pandas as pd

REQUIRED_COLUMNS = {
    "sale_date", "invoice_id", "store_id", "store_name", "product_code", "product_name",
    "category", "customer_id", "quantity", "unit_price_irr", "discount_irr"
}
BUSINESS_COLUMNS = sorted(REQUIRED_COLUMNS)

def load_sales(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"invoice_id": "string", "store_id": "string", "product_code": "string", "customer_id": "string"})
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"ستون‌های ضروری وجود ندارند: {missing}")
    frame = frame.copy()
    if "source_row_id" not in frame:
        frame.insert(0, "source_row_id", range(1, len(frame) + 1))
    frame["sale_date_parsed"] = pd.to_datetime(frame["sale_date"], errors="coerce", format="%Y-%m-%d")
    for column in ["quantity", "unit_price_irr", "discount_irr"]:
        frame[column + "_parsed"] = pd.to_numeric(frame[column], errors="coerce")
    frame["line_gross_irr"] = frame["quantity_parsed"] * frame["unit_price_irr_parsed"]
    frame["line_recorded_value_irr"] = frame["line_gross_irr"] - frame["discount_irr_parsed"]
    frame["is_return_line"] = frame["quantity_parsed"] < 0
    return frame

def _valid_mask(frame: pd.DataFrame) -> pd.Series:
    text_valid = (
        frame["invoice_id"].notna() & frame["invoice_id"].astype("string").str.strip().ne("") &
        frame["store_id"].notna() & frame["store_id"].astype("string").str.strip().ne("") &
        frame["product_code"].notna() & frame["product_code"].astype("string").str.strip().ne("") &
        frame["product_name"].notna() & frame["product_name"].astype("string").str.strip().ne("")
    )
    numbers_valid = (
        frame["quantity_parsed"].notna() & frame["unit_price_irr_parsed"].notna() &
        frame["discount_irr_parsed"].notna() & frame["unit_price_irr_parsed"].ge(0) &
        frame["discount_irr_parsed"].ge(0) & frame["line_recorded_value_irr"].notna() &
        (frame["quantity_parsed"].lt(0).where(frame["quantity_parsed"].notna(), False).eq(False) | frame["discount_irr_parsed"].eq(0))
    )
    return frame["sale_date_parsed"].notna() & text_valid & numbers_valid

def quality_report(frame: pd.DataFrame) -> dict[str, Any]:
    valid = _valid_mask(frame)
    dedupe_fields = [c for c in BUSINESS_COLUMNS if c in frame.columns]
    duplicate_rows = int(frame.duplicated(subset=dedupe_fields, keep="first").sum())
    missing_customer = int(frame["customer_id"].isna().sum() + frame["customer_id"].astype("string").str.strip().eq("").sum())
    total = len(frame)
    return {
        "row_count": total,
        "valid_rows": int(valid.sum()),
        "invalid_rows": int((~valid).sum()),
        "invalid_row_rate": float((~valid).sum() / total) if total else 0.0,
        "exact_duplicate_candidate_rows": duplicate_rows,
        "duplicate_candidate_rate": float(duplicate_rows / total) if total else 0.0,
        "missing_customer_id_rows": missing_customer,
        "missing_customer_rate": float(missing_customer / total) if total else 0.0,
        "validity_rule": "valid date + required invoice/store/product identifiers + parseable quantity/price/discount + nonnegative price/discount; return quantities may be negative only with zero discount",
        "duplicate_rule": "exact duplicate candidates are flagged, never silently deleted",
    }

def analyze_sales(frame: pd.DataFrame, *, start_date: str | None = None, end_date: str | None = None, store_id: str | None = None) -> dict[str, Any]:
    """Compute explicit KPIs. Date filters use Gregorian ISO dates as stored in the source."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    valid = frame.loc[_valid_mask(frame)].copy()
    if start_date:
        valid = valid.loc[valid["sale_date_parsed"] >= pd.Timestamp(start_date)]
    if end_date:
        end = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        valid = valid.loc[valid["sale_date_parsed"] <= end]
    if store_id:
        valid = valid.loc[valid["store_id"].astype(str) == str(store_id)]
    positives = valid.loc[(valid["quantity_parsed"] > 0) & (valid["unit_price_irr_parsed"] > 0)].copy()
    returns = valid.loc[valid["quantity_parsed"] < 0].copy()
    gross_sales = float((positives["quantity_parsed"] * positives["unit_price_irr_parsed"]).sum())
    discounts = float(positives["discount_irr_parsed"].sum())
    positive_net = float(positives["line_recorded_value_irr"].sum())
    signed_recorded = float(valid["line_recorded_value_irr"].sum())
    return_value = float((-returns["line_recorded_value_irr"]).clip(lower=0).sum())
    invoice_count = int(positives["invoice_id"].nunique())
    average_invoice = positive_net / invoice_count if invoice_count else None
    identified = positives.loc[positives["customer_id"].notna() & positives["customer_id"].astype("string").str.strip().ne("")]
    invoice_customer = identified.groupby("customer_id", dropna=True)["invoice_id"].nunique()
    customer_count = int(invoice_customer.index.nunique())
    repeat_customers = int((invoice_customer >= 2).sum())
    repeat_rate = repeat_customers / customer_count if customer_count else None
    if valid.empty:
        monthly, products, stores = [], [], []
    else:
        valid["month"] = valid["sale_date_parsed"].dt.to_period("M").astype(str)
        month_values = valid.groupby("month", as_index=False).agg(net_recorded_irr=("line_recorded_value_irr", "sum"), lines=("invoice_id", "size"))
        months = pd.period_range(valid["sale_date_parsed"].min().to_period("M"), valid["sale_date_parsed"].max().to_period("M"), freq="M").astype(str)
        month_values = month_values.set_index("month").reindex(months, fill_value=0).rename_axis("month").reset_index()
        monthly = [{"month_gregorian": str(r.month), "net_recorded_irr": round(float(r.net_recorded_irr), 2), "line_count": int(r.lines)} for r in month_values.itertuples(index=False)]
        pg = positives.groupby(["product_code", "product_name", "category"], as_index=False).agg(net_sales_irr=("line_recorded_value_irr", "sum"), gross_sales_irr=("line_gross_irr", "sum"), units=("quantity_parsed", "sum"))
        pg = pg.sort_values(["net_sales_irr", "product_code"], ascending=[False, True]).head(10)
        products = [{"product_code": str(r.product_code), "product_name": str(r.product_name), "category": str(r.category), "net_sales_irr": round(float(r.net_sales_irr), 2), "gross_sales_irr": round(float(r.gross_sales_irr), 2), "units": int(r.units)} for r in pg.itertuples(index=False)]
        sg = positives.groupby(["store_id", "store_name"], as_index=False).agg(net_sales_irr=("line_recorded_value_irr", "sum"), invoices=("invoice_id", "nunique"))
        sg = sg.sort_values("net_sales_irr", ascending=False)
        stores = [{"store_id": str(r.store_id), "store_name": str(r.store_name), "net_sales_irr": round(float(r.net_sales_irr), 2), "invoices": int(r.invoices)} for r in sg.itertuples(index=False)]
    return {
        "kpis": {
            "gross_sales_irr": round(gross_sales, 2), "discount_total_irr": round(discounts, 2),
            "positive_net_sales_irr": round(positive_net, 2), "signed_recorded_value_irr": round(signed_recorded, 2),
            "return_value_proxy_irr": round(return_value, 2), "distinct_positive_invoices": invoice_count,
            "average_positive_invoice_value_irr": round(average_invoice, 2) if average_invoice is not None else None,
            "identified_customers": customer_count, "repeat_customers": repeat_customers,
            "repeat_customer_rate": round(repeat_rate, 6) if repeat_rate is not None else None,
            "valid_line_count": int(len(valid)), "positive_sales_line_count": int(len(positives)), "return_line_count": int(len(returns)),
        },
        "quality": quality_report(frame), "monthly_trend": monthly, "top_products": products, "store_performance": stores,
        "filters": {"start_date_gregorian": start_date, "end_date_gregorian": end_date, "store_id": store_id},
        "dataset_classification": "SYNTHETIC DEMONSTRATION DATA — NOT REAL CUSTOMER OR MARKET DATA",
    }
