MODEL (name silver.stg_customer, kind FULL, grain customer_key);

SELECT CAST(c_custkey AS BIGINT) AS customer_key, c_name AS customer_name,
  c_address AS address, c_phone AS phone, c_mktsegment AS market_segment,
  CAST(c_nationkey AS BIGINT) AS nation_key
FROM bronze.customer
