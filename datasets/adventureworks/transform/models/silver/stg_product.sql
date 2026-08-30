MODEL (
  name silver.stg_product,
  kind FULL,
  grain product_id
);

SELECT
  CAST(p.productid AS BIGINT) AS product_id,
  p.name AS product_name,
  pc.name AS category,
  psc.name AS subcategory,
  CAST(p.standardcost AS DECIMAL(18, 4)) AS standard_cost,
  CAST(p.listprice AS DECIMAL(18, 4)) AS list_price
FROM bronze.product AS p
LEFT JOIN bronze.productsubcategory AS psc
  ON p.productsubcategoryid = psc.productsubcategoryid
LEFT JOIN bronze.productcategory AS pc
  ON psc.productcategoryid = pc.productcategoryid
