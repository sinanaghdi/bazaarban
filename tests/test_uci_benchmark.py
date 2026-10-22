import pandas as pd
from bazaarban.uci_benchmark import adapt_uci_online_retail

def test_uci_adapter_preserves_rows_and_marks_missing_source_dimensions():
    source = pd.DataFrame([
        {"InvoiceNo":536365,"StockCode":"85123A","Description":"LIGHT","Quantity":2,"InvoiceDate":"2010-12-01 08:26:00","UnitPrice":2.55,"CustomerID":17850.0,"Country":"United Kingdom"},
        {"InvoiceNo":"C536366","StockCode":"85123A","Description":None,"Quantity":-1,"InvoiceDate":"2010-12-01 08:30:00","UnitPrice":2.55,"CustomerID":None,"Country":"United Kingdom"},
    ])
    adapted=adapt_uci_online_retail(source)
    assert len(adapted)==len(source)
    assert adapted.loc[0,"invoice_id"] == "536365"
    assert adapted.loc[0,"customer_id"] == "17850"
    assert adapted.loc[1,"invoice_id"] == "C536366"
    assert pd.isna(adapted.loc[1,"customer_id"])
    assert pd.isna(adapted.loc[1,"product_name"])
    assert set(adapted["unit_price"].dropna()) == {2.55}
    assert set(adapted["discount"]) == {0.0}
    assert adapted.attrs["currency_code"] == "GBP"

def test_uci_adapter_supports_online_retail_ii_header_aliases():
    source = pd.DataFrame([{
        "Invoice":"C5001","StockCode":"P-1","Description":"Item","Quantity":-2,
        "InvoiceDate":"2010-01-01","Price":4.2,"Customer ID":12345.0,"Country":"UK"
    }])
    adapted=adapt_uci_online_retail(source)
    assert adapted.loc[0,"invoice_id"]=="C5001"
    assert adapted.loc[0,"unit_price"]==4.2
    assert adapted.loc[0,"customer_id"]=="12345"
