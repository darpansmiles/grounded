MODEL (name gold.dim_orderdate, kind FULL, grain order_date_key);

SELECT DISTINCT
  CAST(STRFTIME(order_date, '%Y%m%d') AS BIGINT) AS order_date_key,
  order_date,
  EXTRACT(YEAR FROM order_date) AS order_year,
  EXTRACT(MONTH FROM order_date) AS order_month
FROM silver.stg_orders
