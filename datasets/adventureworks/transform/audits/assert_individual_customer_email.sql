AUDIT (
  name assert_individual_customer_email,
);

SELECT *
FROM @this_model
WHERE customer_type = 'individual'
  AND email IS NULL
