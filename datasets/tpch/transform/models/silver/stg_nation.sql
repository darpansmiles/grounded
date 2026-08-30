MODEL (name silver.stg_nation, kind FULL, grain nation_key);

SELECT CAST(n_nationkey AS BIGINT) AS nation_key, n_name AS nation,
  CAST(n_regionkey AS BIGINT) AS region_key
FROM bronze.nation
