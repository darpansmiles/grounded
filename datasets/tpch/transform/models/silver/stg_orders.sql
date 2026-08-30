MODEL (name silver.stg_orders, kind FULL, grain order_key);

SELECT CAST(o_orderkey AS BIGINT) AS order_key, CAST(o_custkey AS BIGINT) AS customer_key,
  CAST(o_orderdate AS DATE) AS order_date, o_orderstatus AS order_status
FROM bronze.orders
