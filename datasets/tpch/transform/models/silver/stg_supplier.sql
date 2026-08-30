MODEL (name silver.stg_supplier, kind FULL, grain supplier_key);

SELECT CAST(s_suppkey AS BIGINT) AS supplier_key, s_name AS supplier_name,
  s_address AS address, s_phone AS phone, CAST(s_nationkey AS BIGINT) AS nation_key
FROM bronze.supplier
