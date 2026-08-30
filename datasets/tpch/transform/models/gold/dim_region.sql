MODEL (name gold.dim_region, kind FULL, grain region_key);

SELECT region_key, region
FROM silver.stg_region
