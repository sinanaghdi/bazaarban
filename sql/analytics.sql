-- Currency-neutral SQL; values stay in the dataset's source currency.
-- Only positive, non-cancelled rows count as sales. Signed values retain negative rows once.
SELECT
  SUM(CASE WHEN quantity > 0 AND unit_price > 0 AND UPPER(TRIM(COALESCE(invoice_id,''))) NOT LIKE 'C%' THEN quantity * unit_price ELSE 0 END) AS gross_sales,
  SUM(CASE WHEN quantity > 0 AND unit_price > 0 AND UPPER(TRIM(COALESCE(invoice_id,''))) NOT LIKE 'C%' THEN discount ELSE 0 END) AS discount_total,
  SUM(CASE WHEN quantity > 0 AND unit_price > 0 AND UPPER(TRIM(COALESCE(invoice_id,''))) NOT LIKE 'C%' THEN quantity * unit_price - discount ELSE 0 END) AS positive_net_sales,
  SUM(quantity * unit_price - discount) AS signed_recorded_value,
  COUNT(DISTINCT CASE WHEN quantity > 0 AND unit_price > 0 AND UPPER(TRIM(COALESCE(invoice_id,''))) NOT LIKE 'C%' AND invoice_id IS NOT NULL AND TRIM(invoice_id) <> '' THEN invoice_id END) AS distinct_positive_invoices
FROM sales_lines
WHERE sale_date IS NOT NULL AND quantity IS NOT NULL AND unit_price IS NOT NULL AND discount IS NOT NULL;

-- Repeat identified customers divided by identified customers with >= 1 positive invoice.
WITH customer_invoices AS (
  SELECT customer_id, COUNT(DISTINCT invoice_id) AS invoice_count
  FROM sales_lines
  WHERE quantity > 0 AND unit_price > 0
    AND UPPER(TRIM(COALESCE(invoice_id,''))) NOT LIKE 'C%'
    AND invoice_id IS NOT NULL AND TRIM(invoice_id) <> ''
    AND customer_id IS NOT NULL AND TRIM(customer_id) <> ''
    AND sale_date IS NOT NULL
  GROUP BY customer_id
)
SELECT
  SUM(CASE WHEN invoice_count >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
  COUNT(*) AS identified_customers,
  1.0 * SUM(CASE WHEN invoice_count >= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS repeat_customer_rate
FROM customer_invoices;

SELECT SUBSTR(sale_date, 1, 7) AS month_gregorian,
       SUM(quantity * unit_price - discount) AS signed_recorded_value,
       COUNT(*) AS line_count
FROM sales_lines
WHERE sale_date GLOB '????-??-??' AND quantity IS NOT NULL AND unit_price IS NOT NULL AND discount IS NOT NULL
GROUP BY SUBSTR(sale_date, 1, 7)
ORDER BY month_gregorian;
