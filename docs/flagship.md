# Flagship: the governed MCP harness

Grounded's product layer is the governed interface between a model and data.
The data stack provides ingestion, transformation, semantics, and lineage; the
harness turns those assets into a small set of validated calls that can be
executed safely and explained afterwards.

## The model of the world

Two contracts supply the information the harness needs.

- **Contract A** is producer metadata: a source or model run says what dataset
  was produced, its schema and freshness, and the upstream lineage. Runtime
  events are normalized into OpenLineage and served by Marquez.
- **Contract B** is consumer semantics: a metric's definition, dimensions,
  policies, verification rules, owner, and the declared datasets that support
  its citation.

The harness joins the two at query time. It is intentionally not a separate
graph database: Marquez owns the physical lineage graph, Cube owns semantic
exposure, and the harness owns the governed decision at the agent boundary.

For example, the AdventureWorks revenue contract declares the real path:

```
Sales.revenue
  └─ SQLMesh gold.fct_sales
       └─ silver.stg_sales_order_line
            └─ bronze.salesorderdetail
                 └─ PostgreSQL AdventureWorks
```

The completed-order status also reaches `gold.fct_sales` through
`bronze.salesorderheader` and `silver.stg_sales_order`.

## The metric tree

The metric tree is the governed semantic view, not a raw schema browser. It
makes dependencies explicit: Revenue and Orders are parents; AOV inherits their
lineage and policies and computes Revenue / Orders. Additive measures return
zero for empty groups; ratios return null when the denominator is zero. That is
a contract decision, not a model guess.

## The MCP surface

The agent may call only the tools below. The planner's proposed JSON is checked
against the active pack's declared vocabulary before any execution occurs.

| Tool | Purpose |
| --- | --- |
| `list_metrics` | Enumerate declared governed metrics. |
| `describe_metric` | Return a metric definition, dimensions, policy, verification rules, and lineage citation. |
| `query_metric` | Execute one declared metric with declared dimensions and filters. |
| `query_customers` | Run the bounded customer-directory read used for the masking demonstration. |
| `check_policy` | Explain the declared decision for a protected target and role. |
| `impact_of` | Read real downstream lineage from Marquez and map it to active-pack metrics. |
| `search_docs` | Retrieve supporting governance prose; never a source of numbers. |
| `refuse` | The safe outcome when a request cannot map to the governed surface. |

`query_metric` runs in this order:

1. Validate the selected metric, dimensions, filters, and tool arguments.
2. Apply declared row or column policy for the asserted role.
3. Execute through the active metric backend.
4. Verify the returned rows against the metric's declared checks.
5. Append an audit record.
6. Return the answer and its Contract-B citation, with graph-verification status
   when Marquez is available.

The full input/output contract is in [mcp-tools.md](mcp-tools.md).

## What this boundary does and does not do

It governs definitions, policy translation, execution scope, result
verification, audit evidence, and lineage citation. It does not authenticate a
person, establish their identity, sandbox a model, or authorize an out-of-band
action. Those remain responsibilities of surrounding systems. See
[ai-strategy.md](ai-strategy.md) for the operating boundary.

## Why the harness matters

An ungoverned model has to choose a metric interpretation, schema, joins,
filters, SQL dialect, and result explanation in one generation. In Grounded it
only chooses among a declared set of calls. A bad or malformed choice becomes a
refusal; it does not become executable SQL. The evaluation evidence and the
remaining routing limitations are documented in [benchmarks.md](benchmarks.md)
and [error-analysis.md](error-analysis.md).
