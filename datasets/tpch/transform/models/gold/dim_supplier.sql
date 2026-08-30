MODEL (name gold.dim_supplier, kind FULL, grain supplier_key);

SELECT supplier_key, supplier_name, address, phone, nation_key
FROM silver.stg_supplier
