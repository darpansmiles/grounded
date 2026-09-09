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

`python -m evals.benchmark --capture-path <file>` collects the same local
models through both arms and writes complete JSONL execution records. The raw
model receives only the schema and proposes one SQL `SELECT`; the executor opens
DuckDB read-only and rejects multi-statement or non-`SELECT` output before
execution. Collection records the model's actual governed plan and result, plus
the raw SQL attempt, so scoring can be repeated without running a model again.

`python -m evals.compare --capture-path <file>` scores an existing capture
offline. Its independent expected answer uses direct DuckDB SQL rather than the
resolver being evaluated. It reports answer correctness, interface compliance,
policy compliance, and evidence completeness separately, with denominators and
`null` for inapplicable conditional rates. No capture is a valid result card
until the evaluator self-test catches wrong metric, wrong period, duplicate
result, missing evidence, and forbidden scope.

The model can invoke only declared metric calls, so it cannot author free-form
SQL and cannot schema-break. It can still select the wrong declared call and
return a real, governed number for the wrong question. The rebuilt evaluation
measures that answer-level failure; it is not a guarantee. This is a system
comparison, catalog plus governed tools versus schema plus SQL, and does not
isolate the mechanism.

[RERUN: four-dimension comparison table with denominators]

## Faithfulness judge

The optional LLM-as-judge pass asks a local provider whether every claim and
number in each governed or ungoverned answer is supported by the same governed
ground truth. Supply `judge_provider` to `evals.compare.run_comparison` to add
`faithfulness_rate` to the model card; omitting it leaves all existing
correctness, routing, refusal, and safety scores unchanged. This judge is most
useful for interpretive prose and does not replace deterministic row, policy,
and evidence checks.

Before publishing a judge score, the PM should hand-label a small representative
sample and report the judge's agreement with that sample. That spot check is a
PM-owned review step, not automated by this repository.
