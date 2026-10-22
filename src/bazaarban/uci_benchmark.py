"""Adapter for the licensed UCI Online Retail workbook; it does not invent store/currency data."""
from __future__ import annotations
import re
import pandas as pd

EXPECTED_COLUMNS = {
    "InvoiceNo": ("invoiceno", "invoice", "invoice no", "invoice number"),
    "StockCode": ("stockcode", "stock code", "item code"),
    "Description": ("description", "product description", "item description"),
    "Quantity": ("quantity", "qty", "units"),
    "InvoiceDate": ("invoicedate", "invoice date", "date"),
    "UnitPrice": ("unitprice", "unit price", "price"),
    "CustomerID": ("customerid", "customer id", "customer number"),
    "Country": ("country", "customer country"),
}

def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().casefold().replace("_", " "))

def _identifier(value: object):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "<na>"}:
        return pd.NA
    return re.sub(r"\.0$", "", text)

def adapt_uci_online_retail(source: pd.DataFrame) -> pd.DataFrame:
    """Map the UCI schema into Bazaarban's generic amount schema.

    UCI Online Retail describes one online retailer; store fields therefore identify
    the dataset entity, not a physical branch. The source has no category or discount
    column, so category is explicitly unknown and discount is assumed zero solely as
    a schema adapter (not an assertion about actual discounting).
    """
    lookup = {_norm(col): col for col in source.columns}
    rename = {}
    for canonical, aliases in EXPECTED_COLUMNS.items():
        matches = [lookup[_norm_name] for alias in aliases if (_norm_name := _norm(alias)) in lookup]
        if len(matches) != 1:
            raise ValueError(f"UCI Online Retail column {canonical!r} matched {matches}; available={list(source.columns)}")
        rename[matches[0]] = canonical
    if len(set(rename.values())) != len(rename):
        raise ValueError("Source headers map to duplicate canonical fields.")
    frame = source.rename(columns=rename).copy()
    for col in EXPECTED_COLUMNS:
        if col not in frame.columns:
            raise ValueError(f"Missing required UCI source field: {col}")
    dates = pd.to_datetime(frame["InvoiceDate"], errors="coerce", format="mixed")
    customer = frame["CustomerID"].map(_identifier).astype("string")
    result = pd.DataFrame({
        "sale_date": dates.dt.strftime("%Y-%m-%d"),
        "invoice_id": frame["InvoiceNo"].map(_identifier).astype("string"),
        "store_id": "UCI-ONLINE-RETAIL",
        "store_name": "خرده‌فروش آنلاین UCI (یک کسب‌وکار، نه شعبه)",
        "product_code": frame["StockCode"].map(_identifier).astype("string"),
        "product_name": frame["Description"].astype("string").str.strip(),
        "category": "نامشخص (در منبع UCI موجود نیست)",
        "customer_id": customer,
        "quantity": pd.to_numeric(frame["Quantity"], errors="coerce"),
        "unit_price": pd.to_numeric(frame["UnitPrice"], errors="coerce"),
        "discount": 0.0,
    })
    # Preserve missing dates as missing, not the literal string "NaT".
    result["sale_date"] = result["sale_date"].where(dates.notna(), pd.NA)
    result.attrs["currency_code"] = "GBP"
    return result
