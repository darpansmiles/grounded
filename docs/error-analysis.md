# Error Analysis: How Each Arm Fails

The model can invoke only declared metric calls, so it cannot author free-form
SQL and cannot schema-break. It can still select the wrong declared call and
return a real, governed number for the wrong question. The rebuilt evaluation
measures how often that happens; it is not a guarantee.

This document describes the failure taxonomy rather than asserting a headline
rate. The benchmark is a system comparison, catalog plus governed tools versus
schema plus SQL. It does not isolate the mechanism.

## The governed failure mode: a valid call can still be wrong

The governed path separates syntactic validity from answer correctness. A
declared call is well formed and bounded, but it may name the wrong metric,
omit a requested period or dimension, or request a scope the question did not
intend. Those are `wrong_answer` outcomes when the executed rows differ from
the independently computed expected answer. A refusal of an answerable task is
an `over_refusal` outcome.

[RERUN: governed failure taxonomy, including wrong_answer_rate and denominator]

The four scored dimensions stay separate: answer correctness, interface
compliance, policy compliance, and evidence completeness. Each governed answer
carries a definition, a policy record, a verification outcome, and a lineage
citation. Whether that evidence is present, resolves, and matches the
execution is itself measured, not asserted.

## The ungoverned arm: formatting, schema, and answer failures

The raw-SQL control receives a schema and writes a query directly. Its failures
need separate buckets. A fenced or otherwise malformed query can be rejected
before execution. A query can run but refer to a non-existent relation or
column. A query can also execute and still return rows that do not answer the
question. The corrected scorer keeps those modes visible instead of collapsing
them into one reassuring percentage.

[RERUN: ungoverned failure taxonomy by pack, model, and denominator]

A representative historical raw-SQL failure remains useful as an execution
example:

```sql
SELECT SUM(li.revenue - li.cost) AS margin FROM gold.fct_lineitem li GROUP BY 1;
```

`gold.fct_lineitem` does not expose `revenue` or `cost`; the declared columns
are `extended_price`, `discount`, and `supply_cost`. This is a schema failure,
not evidence that a different executable query would have been correct.

## Why the taxonomy matters

`hallucination_rate` in the free-form-SQL sense does not apply to the governed
arm, which cannot author SQL. The governed arm's answer-level failure is a
valid-but-wrong selection (`wrong_answer`), and that rate is measured, not
assumed.

Likewise, a raw model that returns no executable query has not demonstrated
answer correctness. Schema-break, refusal, valid-but-wrong answer, policy
failure, and incomplete evidence each have distinct remediation paths. The
repaired evaluation reports each distribution with its denominator before any
comparison is used as evidence.

## Limits

- The old result cards are superseded because their governed answer-level
  figures were constructed from routing rather than measured execution.
- The rerun reports only the cases and models it actually completes. Incomplete
  cells are not treated as evidence.
- The fixture remains a small deterministic test surface, not a workload claim.
- A judge, if used for interpretive prose, is not an oracle and is reported
  separately from deterministic row, policy, and evidence checks.
