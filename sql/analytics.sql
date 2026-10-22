-- Outputs represent synthetic demo analytics only.
SELECT
  SUM(CASE WHEN quantity > 0 THEN quantity * unit_price_irr ELSE 0 END) AS gross_sales_irr,
  SUM(CASE WHEN quantity > 0 THEN discount_irr ELSE 0 END) AS discount_total_irr,
  SUM(CASE WHEN quantity > 0 THEN quantity * unit_price_irr - discount_irr ELSE 0 END) AS positive_net_sales_irr,
  SUM(quantity * unit_price_irr - discount_irr) AS signed_recorded_value_irr,
  COUNT(DISTINCT CASE WHEN quantity > 0 THEN invoice_id END) AS distinct_positive_invoices
FROM sales_lines;

-- Repeat identified customers divided by identified customers with >= 1 positive invoice.
WITH customer_invoices AS (
  SELECT customer_id, COUNT(DISTINCT invoice_id) AS invoice_count
  FROM sales_lines
  WHERE quantity > 0 AND customer_id IS NOT NULL AND TRIM(customer_id) <> ''
  GROUP BY customer_id
)
SELECT
  SUM(CASE WHEN invoice_count >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
  COUNT(*) AS identified_customers,
  1.0 * SUM(CASE WHEN invoice_count >= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS repeat_customer_rate
FROM customer_invoices;

SELECT SUBSTR(sale_date, 1, 7) AS month_gregorian,
       SUM(quantity * unit_price_irr - discount_irr) AS signed_recorded_value_irr,
       COUNT(*) AS line_count
FROM sales_lines
WHERE sale_date GLOB '????-??-??'
GROUP BY SUBSTR(sale_date, 1, 7)
ORDER BY month_gregorian;
