# AdventureWorks bronze → silver → gold transform

This SQLMesh 0.236.1 project transforms the real AdventureWorks OLTP mirror in
`../data/adventureworks.duckdb`. It owns only the `silver` and `gold` schemas; the
dlt-owned `bronze` schema and Grounded's small `grounded.duckdb` PoC fixture
are separate.

## Run

Run the dlt ingestion before the transform, then materialize and audit the
star schema:

```bash
make ingest
make transform
```

`make transform` runs `sqlmesh plan --auto-apply` followed by all gold-model
audits. SQLMesh uses the DuckDB gateway in `config.yaml`, pointing to
`../data/adventureworks.duckdb` relative to this project.

## DAG and grains

```text
bronze.salesorderheader  -> silver.stg_sales_order -----┐
bronze.salesorderdetail  -> silver.stg_sales_order_line ├-> gold.fct_sales
bronze.product hierarchy -> silver.stg_product ---------┤      │
bronze.customer/person/email -> silver.stg_customer ----┤      ├-> gold.dim_product
bronze.salesterritory    -> silver.stg_territory -------┤      ├-> gold.dim_customer
                                                        └------┴-> gold.dim_territory
silver.stg_sales_order (order-date range) ---------------------> gold.dim_date
```

`gold.fct_sales` is one row per source order detail: `(order_id, line_number)`,
where `line_number` is the AdventureWorks `SalesOrderDetailID`. The dimensional
models use deterministic `ROW_NUMBER` surrogate keys ordered by their natural
keys. `dim_customer` intentionally contains every source customer: 19,119
`individual` members and 701 `store` members. Store accounts have no linked
person/email, so `email` is legitimately nullable for that type.

## Status and revenue contract

`fct_sales.status_code` retains the native AdventureWorks code; `order_status`
maps it to `in_process`, `approved`, `backordered`, `rejected`, `shipped`, or
`cancelled`; and `is_completed` is true only for code `5` (`shipped`). Shipped
is the revenue-recognized state. This sample contains only code `5`, so all
121,317 fact rows have `is_completed = TRUE`; the filter is a no-op in this
sample but correctly excludes rejected, cancelled, and pending states if they
arrive in a later load.

The initial materialization produced:

| Gold relation | Rows |
| --- | ---: |
| `gold.dim_product` | 504 |
| `gold.dim_customer` | 19,820 |
| `gold.dim_territory` | 10 |
| `gold.dim_date` | 1,127 |
| `gold.fct_sales` | 121,317 |

The completed-revenue reference for Slice 024/026 is
`SUM(line_total) WHERE is_completed = TRUE`:

| Category | Revenue |
| --- | ---: |
| Bikes | 94,651,172.72 |
| Components | 11,802,593.29 |
| Clothing | 2,120,542.53 |
| Accessories | 1,272,072.89 |
| **Total** | **109,846,381.43** |

The attached SQLMesh audits prove fact grain uniqueness, non-negative line
totals, non-null/unique surrogate keys for every dimension, and the real email
rule: an `individual` customer must have an email while a `store` customer may
not.

## Static column-lineage handoff for Slice 025

SQLMesh computes lineage from the project model metadata; it does not emit an
OpenLineage file. Slice 025 should use its Python API and normalize the result
to Grounded's Contract-A/OpenLineage shape. From the repository root, the exact
access path validated in this slice is:

```python
from sqlmesh import Context
from sqlmesh.core.lineage import column_dependencies

context = Context(paths="transform")
dependencies = column_dependencies(context, "gold.fct_sales", "line_total")
```

That returns the direct lineage mapping from `gold.fct_sales.line_total` to
`silver.stg_sales_order_line.line_total`; the same call for `is_completed`
returns `silver.stg_sales_order.status_code`. The loaded `Context` supplies
every model and its parsed SQL, so Slice 025 can recursively walk model columns
through `sqlmesh.core.lineage.lineage` / `column_dependencies` before producing
its normalized event for Marquez.
