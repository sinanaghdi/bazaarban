"""تحلیل فروش مستقل از واحد پول، با تفکیک اعتبار مالی از کیفیت شناسه‌ها."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import re
import pandas as pd

COMMON_REQUIRED_COLUMNS = {
    "sale_date", "invoice_id", "store_id", "store_name", "product_code",
    "product_name", "category", "customer_id", "quantity"
}
BUSINESS_COLUMNS = sorted(COMMON_REQUIRED_COLUMNS | {"unit_price_irr", "discount_irr", "unit_price", "discount"})

def _source_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for col in candidates:
        if col in frame.columns:
            return col
    raise ValueError(f"یکی از ستون‌های {candidates} لازم است.")

def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Create common internal names while accepting the legacy IRR CSV and generic benchmark schema."""
    out = frame.copy()
    if "sale_date_parsed" not in out:
        out["sale_date_parsed"] = pd.to_datetime(out["sale_date"], errors="coerce", format="mixed")
    if "quantity_parsed" not in out:
        out["quantity_parsed"] = pd.to_numeric(out["quantity"], errors="coerce")
    price_candidates = ("unit_price_parsed", "unit_price_irr_parsed", "unit_price", "unit_price_irr")
    discount_candidates = ("discount_parsed", "discount_irr_parsed", "discount", "discount_irr")
    price_source = _source_column(out, price_candidates)
    discount_source = _source_column(out, discount_candidates)
    out["unit_price_parsed"] = pd.to_numeric(out[price_source], errors="coerce")
    out["discount_parsed"] = pd.to_numeric(out[discount_source], errors="coerce")
    out["unit_price_irr_parsed"] = out["unit_price_parsed"]  # legacy compatibility for existing callers/tests
    out["discount_irr_parsed"] = out["discount_parsed"]
    out["line_gross_value"] = out["quantity_parsed"] * out["unit_price_parsed"]
    out["line_recorded_value"] = out["line_gross_value"] - out["discount_parsed"]
    out["line_gross_irr"] = out["line_gross_value"]  # legacy result alias
    out["line_recorded_value_irr"] = out["line_recorded_value"]
    out["is_return_line"] = out["quantity_parsed"] < 0
    return out

def load_sales(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"invoice_id": "string", "store_id": "string", "product_code": "string", "customer_id": "string"})
    missing = sorted(COMMON_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"ستون‌های ضروری وجود ندارند: {missing}")
    if not ({"unit_price_irr", "unit_price"} & set(frame.columns)):
        raise ValueError("ستون قیمت واحد وجود ندارد: unit_price یا unit_price_irr لازم است.")
    if not ({"discount_irr", "discount"} & set(frame.columns)):
        raise ValueError("ستون تخفیف وجود ندارد: discount یا discount_irr لازم است.")
    if "source_row_id" not in frame:
        frame.insert(0, "source_row_id", range(1, len(frame) + 1))
    return _prepare_frame(frame)

def _nonempty(series: pd.Series) -> pd.Series:
    return series.notna() & series.astype("string").str.strip().ne("").fillna(False)

def _quality_valid_mask(frame: pd.DataFrame) -> pd.Series:
    df = _prepare_frame(frame)
    text_valid = (
        _nonempty(df["invoice_id"]) & _nonempty(df["store_id"]) &
        _nonempty(df["product_code"]) & _nonempty(df["product_name"])
    )
    numbers_valid = (
        df["quantity_parsed"].notna() & df["unit_price_parsed"].notna() &
        df["discount_parsed"].notna() & df["unit_price_parsed"].ge(0) &
        df["discount_parsed"].ge(0) & df["line_recorded_value"].notna() &
        (df["quantity_parsed"].ge(0) | df["discount_parsed"].eq(0))
    )
    return (df["sale_date_parsed"].notna() & text_valid & numbers_valid).fillna(False)

def _financial_valid_mask(frame: pd.DataFrame) -> pd.Series:
    """Only require a parseable date and computable numeric line value; missing labels are audited separately."""
    df = _prepare_frame(frame)
    return (
        df["sale_date_parsed"].notna() & df["quantity_parsed"].notna() &
        df["unit_price_parsed"].notna() & df["discount_parsed"].notna() &
        df["line_recorded_value"].notna()
    ).fillna(False)

# Kept as a compatibility wrapper for callers that use the project's quality rule.
def _valid_mask(frame: pd.DataFrame) -> pd.Series:
    return _quality_valid_mask(frame)

def quality_report(frame: pd.DataFrame) -> dict[str, Any]:
    df = _prepare_frame(frame)
    valid = _quality_valid_mask(df)
    amount_valid = _financial_valid_mask(df)
    dedupe_fields = [c for c in BUSINESS_COLUMNS if c in df.columns]
    duplicate_rows = int(df.duplicated(subset=dedupe_fields, keep="first").sum()) if dedupe_fields else 0
    missing_customer = int((df["customer_id"].isna() | df["customer_id"].astype("string").str.strip().eq("").fillna(False)).sum())
    missing_product_name = int((df["product_name"].isna() | df["product_name"].astype("string").str.strip().eq("").fillna(False)).sum())
    cancellation = df["invoice_id"].astype("string").str.strip().str.upper().str.startswith("C", na=False)
    total = len(df)
    return {
        "row_count": total,
        "valid_rows": int(valid.sum()),
        "invalid_rows": int((~valid).sum()),
        "invalid_row_rate": float((~valid).sum() / total) if total else 0.0,
        "financially_computable_rows": int(amount_valid.sum()),
        "financially_uncomputable_rows": int((~amount_valid).sum()),
        "exact_duplicate_candidate_rows": duplicate_rows,
        "duplicate_candidate_rate": float(duplicate_rows / total) if total else 0.0,
        "missing_customer_id_rows": missing_customer,
        "missing_customer_rate": float(missing_customer / total) if total else 0.0,
        "missing_product_name_rows": missing_product_name,
        "missing_product_name_rate": float(missing_product_name / total) if total else 0.0,
        "cancellation_invoice_rows": int(cancellation.sum()),
        "negative_quantity_rows": int(df["quantity_parsed"].lt(0).sum()),
        "negative_unit_price_rows": int(df["unit_price_parsed"].lt(0).sum()),
        "validity_rule": "valid date + invoice/store/product identifiers + product name + parseable amount columns + nonnegative price/discount; a return row may not carry a discount",
        "financial_eligibility_rule": "date and arithmetic inputs must be parseable; missing product descriptions remain quality issues but do not remove otherwise computable sales amounts",
        "duplicate_rule": "exact duplicate candidates are flagged, never silently deleted",
    }

def analyze_sales(
    frame: pd.DataFrame,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    store_id: str | None = None,
    currency_code: str | None = None,
    dataset_classification: str = "SYNTHETIC DEMONSTRATION DATA — NOT REAL CUSTOMER OR MARKET DATA",
) -> dict[str, Any]:
    """Compute explicit KPIs; money suffixes follow the dataset's currency, not an exchange-rate conversion."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    df = _prepare_frame(frame)
    source_currency = str(currency_code or frame.attrs.get("currency_code", "IRR")).upper()
    if not re.fullmatch(r"[A-Z]{3}", source_currency):
        raise ValueError("currency_code باید یک کد سه‌حرفی مانند IRR یا GBP باشد.")
    suffix = source_currency.lower()
    valid = df.loc[_financial_valid_mask(df)].copy()
    if start_date:
        valid = valid.loc[valid["sale_date_parsed"] >= pd.Timestamp(start_date)]
    if end_date:
        end = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        valid = valid.loc[valid["sale_date_parsed"] <= end]
    if store_id:
        valid = valid.loc[valid["store_id"].astype(str) == str(store_id)]

    invoice_text = valid["invoice_id"].astype("string").str.strip().str.upper()
    is_cancellation = invoice_text.str.startswith("C", na=False)
    positive_mask = valid["quantity_parsed"].gt(0) & valid["unit_price_parsed"].gt(0) & ~is_cancellation
    positives = valid.loc[positive_mask].copy()
    returns = valid.loc[valid["quantity_parsed"].lt(0)].copy()
    gross_sales = float((positives["quantity_parsed"] * positives["unit_price_parsed"]).sum())
    discounts = float(positives["discount_parsed"].sum())
    positive_net = float(positives["line_recorded_value"].sum())
    signed_recorded = float(valid["line_recorded_value"].sum())
    return_value = float((-returns["line_recorded_value"]).clip(lower=0).sum())

    nonblank_invoice = _nonempty(positives["invoice_id"])
    invoice_count = int(positives.loc[nonblank_invoice, "invoice_id"].nunique())
    invoice_attributed_net = float(positives.loc[nonblank_invoice, "line_recorded_value"].sum())
    average_invoice = invoice_attributed_net / invoice_count if invoice_count else None
    customer_mask = _nonempty(positives["customer_id"]) & nonblank_invoice
    identified = positives.loc[customer_mask]
    invoice_customer = identified.groupby("customer_id", dropna=True)["invoice_id"].nunique()
    customer_count = int(invoice_customer.index.nunique())
    repeat_customers = int((invoice_customer >= 2).sum())
    repeat_rate = repeat_customers / customer_count if customer_count else None

    if valid.empty:
        monthly, products, stores = [], [], []
    else:
        valid["month"] = valid["sale_date_parsed"].dt.to_period("M").astype(str)
        month_values = valid.groupby("month", as_index=False).agg(
            signed_recorded_value=("line_recorded_value", "sum"), lines=("invoice_id", "size")
        )
        months = pd.period_range(valid["sale_date_parsed"].min().to_period("M"), valid["sale_date_parsed"].max().to_period("M"), freq="M").astype(str)
        month_values = month_values.set_index("month").reindex(months, fill_value=0).rename_axis("month").reset_index()
        monthly = [{
            "month_gregorian": str(r.month),
            f"signed_recorded_value_{suffix}": round(float(r.signed_recorded_value), 2),
            "line_count": int(r.lines)
        } for r in month_values.itertuples(index=False)]

        product_source = positives.copy()
        product_source["product_code"] = product_source["product_code"].astype("string").fillna("UNSPECIFIED")
        product_source["product_name"] = product_source["product_name"].astype("string").fillna("بدون توضیح در منبع").replace("", "بدون توضیح در منبع")
        product_source["category"] = product_source["category"].astype("string").fillna("نامشخص").replace("", "نامشخص")
        pg = product_source.groupby(["product_code", "product_name", "category"], as_index=False, dropna=False).agg(
            net_sales=("line_recorded_value", "sum"),
            gross_sales=("line_gross_value", "sum"),
            units=("quantity_parsed", "sum")
        )
        pg = pg.sort_values(["net_sales", "product_code"], ascending=[False, True]).head(10)
        products = [{
            "product_code": str(r.product_code), "product_name": str(r.product_name), "category": str(r.category),
            f"net_sales_{suffix}": round(float(r.net_sales), 2), f"gross_sales_{suffix}": round(float(r.gross_sales), 2),
            "units": float(r.units)
        } for r in pg.itertuples(index=False)]

        store_source = positives.copy()
        store_source["store_id"] = store_source["store_id"].astype("string").fillna("UNSPECIFIED")
        store_source["store_name"] = store_source["store_name"].astype("string").fillna("نامشخص").replace("", "نامشخص")
        sg = store_source.groupby(["store_id", "store_name"], as_index=False, dropna=False).agg(
            net_sales=("line_recorded_value", "sum"), invoices=("invoice_id", "nunique")
        )
        sg = sg.sort_values("net_sales", ascending=False)
        stores = [{
            "store_id": str(r.store_id), "store_name": str(r.store_name),
            f"net_sales_{suffix}": round(float(r.net_sales), 2), "invoices": int(r.invoices)
        } for r in sg.itertuples(index=False)]

    kpis = {
        f"gross_sales_{suffix}": round(gross_sales, 2),
        f"discount_total_{suffix}": round(discounts, 2),
        f"positive_net_sales_{suffix}": round(positive_net, 2),
        f"signed_recorded_value_{suffix}": round(signed_recorded, 2),
        f"return_value_proxy_{suffix}": round(return_value, 2),
        f"average_positive_invoice_value_{suffix}": round(average_invoice, 2) if average_invoice is not None else None,
        f"invoice_attributable_positive_net_sales_{suffix}": round(invoice_attributed_net, 2),
        "distinct_positive_invoices": invoice_count,
        "identified_customers": customer_count,
        "repeat_customers": repeat_customers,
        "repeat_customer_rate": round(repeat_rate, 6) if repeat_rate is not None else None,
        "valid_line_count": int(_quality_valid_mask(df).sum()),
        "financially_computable_line_count": int(len(valid)),
        "positive_sales_line_count": int(len(positives)),
        "return_line_count": int(len(returns)),
        "cancellation_positive_rows_excluded": int(is_cancellation.sum()),
    }
    return {
        "kpis": kpis,
        "quality": quality_report(df),
        "monthly_trend": monthly,
        "top_products": products,
        "store_performance": stores,
        "filters": {"start_date_gregorian": start_date, "end_date_gregorian": end_date, "store_id": store_id},
        "currency_code": source_currency,
        "dataset_classification": dataset_classification,
    }
