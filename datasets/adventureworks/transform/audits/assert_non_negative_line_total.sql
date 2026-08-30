AUDIT (
  name assert_non_negative_line_total,
);

SELECT *
FROM @this_model
WHERE line_total < 0
