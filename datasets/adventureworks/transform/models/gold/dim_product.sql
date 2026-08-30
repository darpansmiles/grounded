MODEL (
  name gold.dim_product,
  kind FULL,
  grain product_key,
  audits (assert_dim_product_key)
);

SELECT
  ROW_NUMBER() OVER (ORDER BY product_id) AS product_key,
  product_id,
  product_name,
  category,
  subcategory,
  standard_cost,
  list_price
FROM silver.stg_product
