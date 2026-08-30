# The two contracts

Grounded uses two deliberately small contracts so the movement, semantics,
lineage, and agent layers can evolve independently.

## Contract A: producer metadata

Contract A is emitted by ingestion and transformation runs. It says what
dataset now exists, its observable shape, where it came from, and which inputs
produced it. The runtime normalizer maps this information into OpenLineage
events for Marquez.

```yaml
event_id: 9f1c...
emitted_at: 2026-08-10T04:12:33Z
producer: sqlmesh
run_id: sqlmesh:2026-08-10T04:12
dataset:
  id: gold.fct_sales
  engine: duckdb
  schema:
    - {name: order_id, type: bigint}
    - {name: line_total, type: decimal(18,4)}
    - {name: is_completed, type: boolean}
  row_count: 121317
lineage:
  inputs:
    - {id: silver.stg_sales_order_line, via: sqlmesh_model:gold.fct_sales}
    - {id: silver.stg_sales_order, via: sqlmesh_model:gold.fct_sales}
  source_systems:
    - {name: postgres.adventureworks, kind: postgres}
quality:
  status: pass
  checks: [assert_fct_sales_grain, assert_non_negative_line_total]
```

Contract A is a producer promise: *this dataset exists, here is its shape and
origin.* It is runtime-derived rather than hand-maintained, so a pack can bring
its own schema without shared-code edits.

## Contract B: governed semantics and policy

Contract B is a metric definition consumed by the governed harness. It states
what can be asked, how it is defined, which policies apply, how a result is
verified, and which real data path supplies its citation.

```yaml
metric: revenue
label: Revenue
description: Gross completed sales revenue.
owner: darpan
definition:
  measure: sum(line_total)
  grain: sales_order_line
  filter: is_completed = TRUE
dimensions:
  - {name: category, source: Products.category}
  - {name: order_month, source: Dates.full_date, granularity: month}
  - {name: country, source: Territories.country_region}
lineage:
  cube_member: Sales.revenue
  model: sqlmesh:gold.fct_sales
  tables: [gold.fct_sales, silver.stg_sales_order_line, bronze.salesorderdetail]
  sources: [postgres.adventureworks]
policies:
  - id: pii-mask-email
    applies_to: customers.email
    rule: mask
    unless_role: [analyst_pii, admin]
  - id: row-eu-only
    applies_to: customers.country
    cube_member: Sales.country
    rule: row_filter
    predicate: "country IN ('DE','FR','NL')"
    when_role: [eu_analyst]
verification:
  - {type: non_negative, field: revenue}
  - {type: not_null, field: category}
```

Contract B is a consumer promise: *this is a governed metric, its policies,
lineage, and checks.* Cube supplies the semantic model; the harness reads the
contract, never invents a measure, and returns the citation alongside results.

## The seam

Contract A describes produced datasets. Contract B describes the governed
meaning of a metric. Marquez validates and serves the graph implied by the
first, while the metric resolver and harness execute the second. Their joining
point is explicit rather than an undocumented coupling between tools.
