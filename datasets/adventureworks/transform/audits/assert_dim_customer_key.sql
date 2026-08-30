AUDIT (
  name assert_dim_customer_key,
);

SELECT customer_key
FROM @this_model
GROUP BY customer_key
HAVING customer_key IS NULL OR COUNT(*) > 1
