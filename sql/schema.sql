-- SQLite-compatible analytical schema.
-- Monetary columns are currency-neutral and preserve the source unit (for example GBP or IRR).
-- Ingestion should retain source anomalies; validation rules flag them rather than rejecting rows.
CREATE TABLE IF NOT EXISTS sales_lines (
  source_row_id INTEGER PRIMARY KEY,
  sale_date TEXT,
  invoice_id TEXT,
  store_id TEXT,
  store_name TEXT,
  product_code TEXT,
  product_name TEXT,
  category TEXT,
  customer_id TEXT,
  quantity REAL,
  unit_price REAL,
  discount REAL
);
CREATE INDEX IF NOT EXISTS ix_sales_lines_date ON sales_lines(sale_date);
CREATE INDEX IF NOT EXISTS ix_sales_lines_invoice ON sales_lines(invoice_id);
CREATE INDEX IF NOT EXISTS ix_sales_lines_store ON sales_lines(store_id);
