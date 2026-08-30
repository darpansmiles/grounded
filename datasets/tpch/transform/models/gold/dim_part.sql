MODEL (name gold.dim_part, kind FULL, grain part_key);

SELECT part_key, part_name, part_brand, part_type, part_size
FROM silver.stg_part
