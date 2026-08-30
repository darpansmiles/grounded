MODEL (name silver.stg_part, kind FULL, grain part_key);

SELECT CAST(p_partkey AS BIGINT) AS part_key, p_name AS part_name,
  p_brand AS part_brand, p_type AS part_type, CAST(p_size AS INTEGER) AS part_size
FROM bronze.part
