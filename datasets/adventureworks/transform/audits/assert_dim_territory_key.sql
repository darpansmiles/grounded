AUDIT (
  name assert_dim_territory_key,
);

SELECT territory_key
FROM @this_model
GROUP BY territory_key
HAVING territory_key IS NULL OR COUNT(*) > 1
