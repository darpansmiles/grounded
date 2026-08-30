MODEL (
  name silver.stg_customer,
  kind FULL,
  grain customer_id
);

SELECT
  CAST(c.customerid AS BIGINT) AS customer_id,
  CASE
    WHEN c.personid IS NULL THEN 'store'
    ELSE 'individual'
  END AS customer_type,
  NULLIF(CONCAT_WS(' ', p.firstname, p.lastname), '') AS full_name,
  e.emailaddress AS email
FROM bronze.customer AS c
LEFT JOIN bronze.person AS p
  ON c.personid = p.businessentityid
LEFT JOIN bronze.emailaddress AS e
  ON p.businessentityid = e.businessentityid
