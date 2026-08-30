MODEL (
  name silver.stg_sales_order_line,
  kind FULL,
  grain (order_id, line_number)
);

SELECT
  CAST(salesorderid AS BIGINT) AS order_id,
  CAST(salesorderdetailid AS BIGINT) AS line_number,
  CAST(productid AS BIGINT) AS product_id,
  CAST(orderqty AS INTEGER) AS quantity,
  CAST(unitprice AS DECIMAL(18, 4)) AS unit_price,
  CAST(linetotal AS DECIMAL(18, 4)) AS line_total
FROM bronze.salesorderdetail
