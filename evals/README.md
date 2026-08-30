# Eval harness

This harness runs the deterministic agent against PM-authored golden questions,
captures one append-only JSONL trace per case, and scores governed correctness:
metric rows, verification, lineage citation, policy behavior, metric description,
and safe refusals. A deliberately failing paraphrase is a known gap, so it is
visible without counting as an unexpected failure.

Run the deterministic fixture first, then run the harness:

```bash
python scripts/seed_duckdb.py
python -m evals.runner
```

## Scorecard metrics

`python -m evals.scorecard` runs the golden set again, then computes and writes
`evals/scorecard.json` for that fresh run. It reports correctness and
citation-correctness both including and excluding known gaps; policy-compliance;
appropriate refusals and over-refusals; and latency p50/p95/max plus cost total
and mean. Latency percentiles use nearest-rank calculation, so distributions
rather than a single average remain visible.

The scorecard is keyed by the trace `model` (`deterministic-planner` today), so
later model/prompt versions can be compared without changing the metric shape.

## Error taxonomy

`python -m evals.error_report` runs the golden set and writes
`evals/error_analysis.json`. It labels every trace as correct, over- or
under-refusal, policy violation, verification failure, wrong number, missing
citation, or uncategorized. The report keeps known gaps separate from real
failures so the current paraphrase over-refusal remains visible without being
misreported as a regression.

Later slices add LLM-as-judge and model routing.

## Governed multi-model routing benchmark

`python -m evals.benchmark` runs `golden_v2.yml` three times for the
deterministic baseline and each local Ollama tier, then writes
`evals/benchmark.json` and prints a comparison table. It measures routing
accuracy, appropriate and over-refusal rates, schema compliance, and p50/p95
latency, retaining a scorecard and samples for each run so variance is visible.

| Tier | Ollama model | Benchmark question |
| --- | --- | --- |
| Entry | `llama3.2:3b` | Can a tiny model route reliably behind the harness? |
| Schema | `qwen2.5:7b` | Does it produce compliant governed call JSON? |
| Frontier-local | `phi4:latest` | Does more raw capability improve governed routing? |

Start Ollama and pull any desired models before the real run. A missing local
model is recorded as `skipped` with a reason (`request_error`, `zero_samples`,
or `timeout`), never treated as a benchmark crash. Use conservative
`OLLAMA_NUM_PARALLEL` values: 3–4 for models up to 3B, 2 for 7–9B, and 1 for
13B+ models. Larger models can OOM when parallel requests allocate several
KV-caches. This is the
**governed** arm only: every produced call passes the Slice 011 guardrail before
scoring. Slice 012b adds the ungoverned control arm.

## Ungoverned control arm and model card

`python -m evals.compare` runs the same local models without the governed
harness. The raw model receives only the fixture schema and proposes one SQL
`SELECT`; the executor opens DuckDB read-only and rejects multi-statement or
non-`SELECT` output before execution. Metric-case ground truth is computed by
the governed resolver using Golden-v2's expected plan and role. Refusal cases
have no valid answer, so any raw answer is a hallucination.

The command writes `evals/model_card.json` and prints governed/ungoverned
columns for the `correct_answer`, `correct_refusal`, `hallucination`,
`over_refusal`, and `schema_break` outcome rates. The headline is
`hallucination_rate`: governed calls cannot fabricate a number, while
ungoverned raw SQL can. Governed `routing_accuracy` and conditional
`answer_correctness_when_answered` remain visible so safety is not mistaken for
coverage. The deterministic keyword planner is a 012a routing floor only; this
same-model raw-SQL comparison runs the three local tiers. Describe, impact, and
policy cases are intentionally excluded because they are governed meta-tools,
not raw SQL questions. This control arm is the comparison for the governed
benchmark; it does not make raw SQL available to the production agent.

## Faithfulness judge

The optional LLM-as-judge pass asks a local provider whether every claim and
number in each governed or ungoverned answer is supported by the same governed
ground truth. Supply `judge_provider` to `evals.compare.run_comparison` to add
`faithfulness_rate` to the model card; omitting it leaves all existing
correctness, routing, refusal, and safety scores unchanged. This judge is most
useful for identifying ungoverned fabricated answers; governed results remain
faithful by construction.

Before publishing a judge score, the PM should hand-label a small representative
sample and report the judge's agreement with that sample. That spot check is a
PM-owned review step, not automated by this repository.
