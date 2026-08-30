MODEL (
  name gold.dim_date,
  kind FULL,
  grain date_key,
  audits (assert_dim_date_key)
);

WITH date_bounds AS (
  SELECT
    MIN(order_date) AS min_order_date,
    MAX(order_date) AS max_order_date
  FROM silver.stg_sales_order
)
SELECT
  CAST(STRFTIME(calendar.full_date, '%Y%m%d') AS BIGINT) AS date_key,
  calendar.full_date,
  EXTRACT(YEAR FROM calendar.full_date) AS year,
  EXTRACT(MONTH FROM calendar.full_date) AS month,
  EXTRACT(QUARTER FROM calendar.full_date) AS quarter
FROM date_bounds
CROSS JOIN GENERATE_SERIES(
  min_order_date,
  max_order_date,
  INTERVAL '1 day'
) AS calendar(full_date)
