# Governed MCP tools

The planner may propose one JSON object shaped as `{"tool": "…", "args": {…}}`. The harness validates the tool and arguments against the active pack before it performs any execution. It never accepts raw SQL.

| Tool | Inputs | Success result | Failure / boundary |
| --- | --- | --- | --- |
| `list_metrics` | `{}` | Declared metric names, labels, descriptions, and owners. | Returns only metrics in the active pack. |
| `describe_metric` | `metric` | Definition, dimensions, policies, checks, Contract-B citation, and graph-verification state. | Unknown metrics are rejected. |
| `query_metric` | `metric`, optional `dimensions`, optional declared `filters`, optional `role` | Result rows, policy decisions, verification evidence, audit record, citation, and graph state. | Unknown metric, dimension, or filter is rejected before execution. |
| `query_customers` | optional `role` | The bounded customer-directory demonstration with masking decisions. | It is not a general table reader. |
| `check_policy` | `target`, `role` | Declared allow, mask, row-filter, or deny decision and reason. | An undeclared target returns the explicit no-policy decision. |
| `impact_of` | declared lineage `dataset` | Marquez-derived downstream datasets and active-pack metrics. | Returns unavailable, empty collections if lineage service is unavailable. |
| `search_docs` | `query`, optional positive `k` | Cited governance and definition prose. | It is supporting context, never a numeric source. |
| `refuse` | `{}` | Safe non-answer. | Used when a request cannot map to exactly one governed call. |

`query_metric` is the key boundary: policy is applied before execution; declared result checks run afterwards; and the final response includes its audit and citation context. A planner can lose coverage through refusal, but it cannot turn an undeclared metric or an arbitrary SQL statement into a query.
