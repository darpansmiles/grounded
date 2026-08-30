AUDIT (
  name assert_dim_product_key,
);

SELECT product_key
FROM @this_model
GROUP BY product_key
HAVING product_key IS NULL OR COUNT(*) > 1
