MODEL (
  name gold.fct_sales,
  kind FULL,
  grain (order_id, line_number),
  audits (assert_fct_sales_grain, assert_non_negative_line_total)
);

SELECT
  dp.product_key,
  dc.customer_key,
  dt.territory_key,
  dd.date_key,
  line.order_id,
  line.line_number,
  orders.order_date,
  line.quantity,
  line.unit_price,
  line.line_total,
  dp.standard_cost,
  orders.status_code,
  CASE orders.status_code
    WHEN 1 THEN 'in_process'
    WHEN 2 THEN 'approved'
    WHEN 3 THEN 'backordered'
    WHEN 4 THEN 'rejected'
    WHEN 5 THEN 'shipped'
    WHEN 6 THEN 'cancelled'
    ELSE 'unknown'
  END AS order_status,
  orders.status_code = 5 AS is_completed
FROM silver.stg_sales_order_line AS line
JOIN silver.stg_sales_order AS orders
  ON line.order_id = orders.order_id
JOIN gold.dim_product AS dp
  ON line.product_id = dp.product_id
JOIN gold.dim_customer AS dc
  ON orders.customer_id = dc.customer_id
JOIN gold.dim_territory AS dt
  ON orders.territory_id = dt.territory_id
JOIN gold.dim_date AS dd
  ON orders.order_date = dd.full_date
