# Grounded data dictionary

## Revenue

Revenue means gross merchandise revenue from completed order items. It is the sum of item quantity multiplied by unit price, and excludes orders that are not completed.

## Orders

Orders means the count of distinct completed orders.

## Average Order Value (AOV)

Average Order Value (AOV) means revenue divided by orders, using completed orders for both inputs.

## Category

Category is the product category associated with an order item, such as Electronics, Home, or Books.

## PII masking

Customer email is personally identifiable information (PII). It is masked for ordinary viewers and is unmasked only for the asserted `analyst_pii` or `admin` role.
