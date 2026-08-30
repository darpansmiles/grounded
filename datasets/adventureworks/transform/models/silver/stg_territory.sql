MODEL (
  name silver.stg_territory,
  kind FULL,
  grain territory_id
);

SELECT
  CAST(territoryid AS BIGINT) AS territory_id,
  name AS territory_name,
  countryregioncode AS country_region
FROM bronze.salesterritory
