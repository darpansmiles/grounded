MODEL (
  name silver.stg_sales_order,
  kind FULL,
  grain order_id
);

SELECT
  CAST(salesorderid AS BIGINT) AS order_id,
  CAST(orderdate AS DATE) AS order_date,
  CAST(status AS INTEGER) AS status_code,
  CAST(customerid AS BIGINT) AS customer_id,
  CAST(territoryid AS BIGINT) AS territory_id
FROM bronze.salesorderheader
