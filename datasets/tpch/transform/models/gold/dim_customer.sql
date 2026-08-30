MODEL (name gold.dim_customer, kind FULL, grain customer_key);

SELECT customer_key, customer_name, address, phone, market_segment, nation_key
FROM silver.stg_customer
