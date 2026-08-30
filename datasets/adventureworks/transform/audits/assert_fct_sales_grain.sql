AUDIT (
  name assert_fct_sales_grain,
);

SELECT
  order_id,
  line_number
FROM @this_model
GROUP BY
  order_id,
  line_number
HAVING COUNT(*) > 1
