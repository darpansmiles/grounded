MODEL (name gold.fct_lineitem, kind FULL, grain (order_key, line_number));

SELECT
  line.order_key,
  line.line_number,
  line.part_key,
  line.supplier_key,
  orders.customer_key,
  customer.nation_key,
  nation.region_key,
  CAST(STRFTIME(orders.order_date, '%Y%m%d') AS BIGINT) AS order_date_key,
  line.quantity,
  line.extended_price,
  line.discount,
  line.tax,
  supply.supply_cost,
  line.ship_date,
  orders.order_status,
  orders.order_status = 'F' AS is_completed
FROM silver.stg_lineitem AS line
JOIN silver.stg_orders AS orders ON line.order_key = orders.order_key
JOIN silver.stg_partsupp AS supply
  ON line.part_key = supply.part_key AND line.supplier_key = supply.supplier_key
JOIN gold.dim_part AS part ON line.part_key = part.part_key
JOIN gold.dim_supplier AS supplier ON line.supplier_key = supplier.supplier_key
JOIN gold.dim_customer AS customer ON orders.customer_key = customer.customer_key
JOIN gold.dim_nation AS nation ON customer.nation_key = nation.nation_key
JOIN gold.dim_region AS region ON nation.region_key = region.region_key
JOIN gold.dim_orderdate AS orderdate
  ON orders.order_date = orderdate.order_date
