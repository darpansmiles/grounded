AUDIT (
  name assert_dim_date_key,
);

SELECT date_key
FROM @this_model
GROUP BY date_key
HAVING date_key IS NULL OR COUNT(*) > 1
