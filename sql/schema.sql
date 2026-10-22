-- SQLite-compatible teaching schema. Dates are stored as ISO Gregorian YYYY-MM-DD.
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
  quantity INTEGER,
  unit_price_irr INTEGER,
  discount_irr INTEGER,
  CHECK (unit_price_irr IS NULL OR unit_price_irr >= 0),
  CHECK (discount_irr IS NULL OR discount_irr >= 0)
);
CREATE INDEX IF NOT EXISTS ix_sales_lines_date ON sales_lines(sale_date);
CREATE INDEX IF NOT EXISTS ix_sales_lines_invoice ON sales_lines(invoice_id);
CREATE INDEX IF NOT EXISTS ix_sales_lines_store ON sales_lines(store_id);
