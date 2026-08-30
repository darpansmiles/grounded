MODEL (name silver.stg_lineitem, kind FULL, grain (order_key, line_number));

SELECT CAST(l_orderkey AS BIGINT) AS order_key, CAST(l_partkey AS BIGINT) AS part_key,
  CAST(l_suppkey AS BIGINT) AS supplier_key, CAST(l_linenumber AS INTEGER) AS line_number,
  CAST(l_quantity AS DECIMAL(18, 4)) AS quantity,
  CAST(l_extendedprice AS DECIMAL(18, 4)) AS extended_price,
  CAST(l_discount AS DECIMAL(18, 4)) AS discount,
  CAST(l_tax AS DECIMAL(18, 4)) AS tax, CAST(l_shipdate AS DATE) AS ship_date
FROM bronze.lineitem
