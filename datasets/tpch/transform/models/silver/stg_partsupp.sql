MODEL (name silver.stg_partsupp, kind FULL, grain (part_key, supplier_key));

SELECT CAST(ps_partkey AS BIGINT) AS part_key, CAST(ps_suppkey AS BIGINT) AS supplier_key,
  CAST(ps_supplycost AS DECIMAL(18, 4)) AS supply_cost
FROM bronze.partsupp
