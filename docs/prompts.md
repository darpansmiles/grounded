# Prompts and guardrails

Prompts tell a model what surface it may use; runtime validation decides whether that proposal can execute. The active dataset pack supplies the metric, dimension, filter, policy-target, and lineage vocabulary.

## Governed planner prompt

The planner is rendered at runtime from the active pack. Its stable instruction is:

```text
You are a planner for Grounded. Return one JSON object with exactly
{"tool": "...", "args": {...}}.
Use only declared tools, metrics, dimensions, and filters. Never emit SQL,
database commands, extra arguments, or tools outside this list. If the question
cannot be mapped to one call, return {"tool":"refuse","args":{}}.
```

The rendered prompt enumerates `list_metrics`, `describe_metric`, `query_metric`, `query_customers`, `check_policy`, `impact_of`, `search_docs`, and the active Contract-B vocabulary. Parsing plus schema validation turns any malformed or undeclared proposal into `refuse`.

## Raw-SQL control prompt

The comparison arm is given the active DuckDB schema including relation names, columns, and types; key-join guidance; three generic SQL examples; and this instruction:

```text
Answer the user's question by returning one SQL SELECT statement.
Return SQL only. You may use joins and aggregations, but do not use markdown or explanations.
```

The runner allows one `SELECT` or `WITH` statement, executes it read-only, and gives one bounded retry with the returned database error. This is why schema-break is separately measured instead of quietly discarding failures.

## Prompt ablation

The governed ablation uses four pack-driven variants:

| Variant | Construction |
| --- | --- |
| `minimal` | Declared metrics and dimensions plus the compact tool contract. |
| `027-generalized` | The full generated planner prompt. |
| `verbose` | The full prompt plus an explicit map-to-one-tool reminder. |
| `adversarial-terse` | The compact surface plus instructions to refuse bypass, SQL, invented data, and undeclared tools. |

The ablation measures routing accuracy; safety does not depend on a preferred wording because validated execution prevents invalid plans from running.
