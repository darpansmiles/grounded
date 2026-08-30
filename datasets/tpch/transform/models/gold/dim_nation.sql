MODEL (name gold.dim_nation, kind FULL, grain nation_key);

SELECT nation_key, nation, region_key
FROM silver.stg_nation
