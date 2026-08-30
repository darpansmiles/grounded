MODEL (name silver.stg_region, kind FULL, grain region_key);

SELECT CAST(r_regionkey AS BIGINT) AS region_key, r_name AS region
FROM bronze.region
