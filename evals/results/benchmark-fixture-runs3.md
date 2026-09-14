# Fixture benchmark result

- dataset: Fixture
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- scoring commit: `101e056caec9863f9f14016565f1d6982e4fdbfb`
- rendered at commit: `ebbcf12`
- capture SHA-256: `22ab8c857a43b34de5d11541e88f22f30b85d9fc23eb9acdf92398e3e9c590d1`
- dataset snapshot: `datasets/fixture` tree `55c04265fd544f017c0826c3f2fcd9c4f29397e0`
- publication gate: unscorable governed=0, raw=0; recovery errors governed=0, raw=0
- reproduction: `.venv/bin/python -m evals.benchmark --dataset fixture --runs 3 --capture-path .grounded/captures/fixture-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/fixture-final-r3.jsonl --recover-raw --recover-governed --offline-output .grounded/scores/fixture-final-r3-review.json` (Cube must be running for governed recovery.)

This deterministic pack has 30 in-catalog cases per model. Its small
denominators make it a harness test surface, not a workload claim. Correct is
conditional on answered in-catalog cases; policy has 3 applicable cases.

Applicable denominators range from 3 to 30 cases per model, so the near-100%
governed figures are low-N and should not be read as workload evidence.

| Model | Gov. correct | Gov. wrong | Interface | Policy | Evidence | Raw SQL correct | Raw SQL wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma2:9b | 100.0% (3/3) | 0.0% (0/30) | 100.0% (30/30) | 0.0% (0/3) | 10.0% (3/30) | 0.0% (0/15) | 50.0% (15/30) |
| llama3.1:8b | 100.0% (30/30) | 0.0% (0/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 0.0% (0/15) | 50.0% (15/30) |
| llama3.2:3b | 80.0% (24/30) | 20.0% (6/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 0.0% (0/24) | 80.0% (24/30) |
| mistral:7b | 80.0% (24/30) | 20.0% (6/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 0.0% (0/12) | 40.0% (12/30) |
| phi3.5 | 100.0% (6/6) | 0.0% (0/30) | 100.0% (30/30) | 0.0% (0/3) | 20.0% (6/30) | NA (0/0) | 0.0% (0/30) |
| phi4 | 100.0% (30/30) | 0.0% (0/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 0.0% (0/27) | 90.0% (27/30) |
| qwen2.5:14b | 100.0% (30/30) | 0.0% (0/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 12.5% (3/24) | 70.0% (21/30) |
| qwen2.5:3b | 100.0% (9/9) | 0.0% (0/30) | 90.0% (27/30) | 0.0% (0/3) | 30.0% (9/30) | NA (0/0) | 0.0% (0/30) |
| qwen2.5:7b | 100.0% (9/9) | 0.0% (0/30) | 100.0% (30/30) | 0.0% (0/3) | 30.0% (9/30) | 0.0% (0/3) | 10.0% (3/30) |
