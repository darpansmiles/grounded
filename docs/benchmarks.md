# Benchmarks

The benchmark asks the same golden-set questions of two arms. The governed arm must emit a valid, pack-driven MCP plan; a validated plan is executed through the governed metric surface and every other plan becomes a refusal. The control arm receives the active DuckDB schema, a clear instruction to return one SQL `SELECT`, generic SQL examples, and one bounded retry after an execution error. It is a steelmanned raw-SQL comparison, not a weak prompt.

## Method

- **Datasets:** AdventureWorks, TPC-H, Spider `world_1`, BIRD `california_schools`, and the deterministic fixture.
- **Models:** `llama3.2:3b`, `qwen2.5:3b`, `qwen2.5:7b`, `qwen2.5:14b`, `llama3.1:8b`, `gemma2:9b`, `mistral:7b`, `phi3.5`, and `phi4` when the local machine completed the run.
- **Runs:** three per golden case. Golden truth is computed from the governed backend, not supplied to the planner.
- **Reporting:** mutually exclusive failure labels; bootstrap confidence intervals; exact paired McNemar tests; local LLM-judge faithfulness with agreement against hand labels; and a four-variant planner prompt ablation.

The detailed taxonomy is defined in [metrics.md](metrics.md). The judge is an additional measurement, not an oracle.

## Recorded result ranges

Each completed governed cell has a 0.0% hallucination rate. The ranges below are the corresponding ungoverned rates from the result cards; they are ranges across completed models, not averages.

| Dataset | Completed models | Governed hallucination | Ungoverned hallucination range |
| --- | ---: | ---: | ---: |
| AdventureWorks | 6 / 9 | 0.0% | 52.2%–97.8% |
| TPC-H | 9 / 9 | 0.0% | 0.0%–100.0% |
| Spider `world_1` | 9 / 9 | 0.0% | 0.0%–97.7% |
| BIRD `california_schools` | 8 / 9 | 0.0% | 33.3%–72.2% |
| Fixture | 8 / 9 | 0.0% | 0.0%–75.0% |

On the full TPC-H card, the governed rates are 0.0% for all nine models while the ungoverned arm ranges from 50.6% to 100.0% when the all-schema-break phi4 outcome is read separately. Exact McNemar tests have zero discordance in the governed-wrong direction for the completed paired cases; for example the TPC-H `qwen2.5:14b` comparison reports b=249, c=0, p=2.21086e-75.

The raw cards are retained as local run artifacts; this page transcribes the public summary so it remains useful after a fresh clone.

## What the control arm actually broke

The raw-SQL arm most often produced non-executable output, including **408** TPC-H and **198** Spider occurrences of `only one SELECT statement is allowed`. It also invented relations and columns, including the recorded TPC-H errors `Referenced column "part_type" not found in FROM clause` (27) and `Referenced column "part_brand" not found in FROM clause` (24).

One representative rejected TPC-H output was:

```sql
SELECT SUM(li.revenue - li.cost) AS margin FROM gold.fct_lineitem li GROUP BY 1;
```

The relation does not expose `revenue` or `cost`; the executed schema uses different fields. This is a schema-break, not a plausible numeric result.

## How to read the zeroes

Phi4's 0.0% ungoverned hallucination on TPC-H and Spider is not a safety win: its schema-break rate on those cards is 100.0%, so it never reached an answer that could be counted as a fabricated value. Always read hallucination next to schema-break and coverage.

Likewise, governed 0.0% is a safety property of the validated execution path, not a claim that every request is useful. A weak model can over-refuse. On the AdventureWorks result, `qwen2.5:3b` routed 19.8% of requests correctly and over-refused 68.9%, while its executed answers remained correct.

## Caveats

- AdventureWorks has 6 of 9 completed model comparisons; slow local runs did not complete the remaining cells.
- RSS and CPU figures in the cards sample the benchmark harness process, not the loaded model server, so they are not model-memory measurements.
- The fixture is intentionally small and deterministic; it validates the mechanism, not real-world coverage.
- Routing quality depends on the model and vocabulary. Governance removes the raw-SQL execution path; it does not make a poor router useful.

For the narrative failure analysis, see [error-analysis.md](error-analysis.md).
