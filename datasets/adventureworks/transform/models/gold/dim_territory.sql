MODEL (
  name gold.dim_territory,
  kind FULL,
  grain territory_key,
  audits (assert_dim_territory_key)
);

SELECT
  ROW_NUMBER() OVER (ORDER BY territory_id) AS territory_key,
  territory_id,
  territory_name,
  country_region
FROM silver.stg_territory
