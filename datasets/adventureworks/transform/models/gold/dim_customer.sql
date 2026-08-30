MODEL (
  name gold.dim_customer,
  kind FULL,
  grain customer_key,
  audits (assert_dim_customer_key, assert_individual_customer_email)
);

SELECT
  ROW_NUMBER() OVER (ORDER BY customer_id) AS customer_key,
  customer_id,
  customer_type,
  full_name,
  email
FROM silver.stg_customer
