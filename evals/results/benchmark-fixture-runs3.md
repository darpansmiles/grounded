# Fixture benchmark result

- dataset: Fixture
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- scoring commit: `101e056caec9863f9f14016565f1d6982e4fdbfb`
- rendered at commit: `a6a23dd`
- capture SHA-256: `22ab8c857a43b34de5d11541e88f22f30b85d9fc23eb9acdf92398e3e9c590d1`
- dataset snapshot: `datasets/fixture` tree `55c04265fd544f017c0826c3f2fcd9c4f29397e0`
- publication gate: unscorable governed=0, raw=0; recovery errors governed=0, raw=0
- reproduction: `.venv/bin/python -m evals.benchmark --dataset fixture --runs 3 --capture-path .grounded/captures/fixture-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/fixture-final-r3.jsonl --recover-raw --recover-governed --offline-output .grounded/scores/fixture-final-r3-review.json` (Cube must be running for governed recovery.)

This deterministic pack has 30 in-catalog attempts per model. Its
small denominators make it a harness test surface, not a workload claim.
Primary correctness is correct / all; policy has 3 applicable cases.

Applicable denominators range from 3 to 30 attempts per model, so the
near-100% governed figures are low-N and should not be read as workload
evidence.

## Primary correctness

| Model | Attempts | Governed correct / all | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 30 | 10.0% (3/30) | 0.0% (0/30) |
| llama3.1:8b | 30 | 100.0% (30/30) | 0.0% (0/30) |
| llama3.2:3b | 30 | 80.0% (24/30) | 0.0% (0/30) |
| mistral:7b | 30 | 80.0% (24/30) | 0.0% (0/30) |
| phi3.5 | 30 | 20.0% (6/30) | 0.0% (0/30) |
| phi4 | 30 | 100.0% (30/30) | 0.0% (0/30) |
| qwen2.5:14b | 30 | 100.0% (30/30) | 10.0% (3/30) |
| qwen2.5:3b | 30 | 30.0% (9/30) | 0.0% (0/30) |
| qwen2.5:7b | 30 | 30.0% (9/30) | 0.0% (0/30) |

## Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all | Interface | Policy | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 10.0% (3/30) | 100.0% (3/3) | 0.0% (0/30) | 90.0% (27/30) | 50.0% (15/30) | 0.0% (0/15) | 50.0% (15/30) | 50.0% (15/30) | 100.0% (30/30) | 0.0% (0/3) | 10.0% (3/30) |
| llama3.1:8b | 100.0% (30/30) | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/30) | 50.0% (15/30) | 0.0% (0/15) | 50.0% (15/30) | 50.0% (15/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) |
| llama3.2:3b | 100.0% (30/30) | 80.0% (24/30) | 20.0% (6/30) | 0.0% (0/30) | 80.0% (24/30) | 0.0% (0/24) | 80.0% (24/30) | 20.0% (6/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) |
| mistral:7b | 100.0% (30/30) | 80.0% (24/30) | 20.0% (6/30) | 0.0% (0/30) | 40.0% (12/30) | 0.0% (0/12) | 40.0% (12/30) | 60.0% (18/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) |
| phi3.5 | 20.0% (6/30) | 100.0% (6/6) | 0.0% (0/30) | 80.0% (24/30) | 0.0% (0/30) | NA (0/0) | 0.0% (0/30) | 100.0% (30/30) | 100.0% (30/30) | 0.0% (0/3) | 20.0% (6/30) |
| phi4 | 100.0% (30/30) | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/30) | 90.0% (27/30) | 0.0% (0/27) | 90.0% (27/30) | 10.0% (3/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) |
| qwen2.5:14b | 100.0% (30/30) | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/30) | 80.0% (24/30) | 12.5% (3/24) | 70.0% (21/30) | 20.0% (6/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) |
| qwen2.5:3b | 30.0% (9/30) | 100.0% (9/9) | 0.0% (0/30) | 70.0% (21/30) | 0.0% (0/30) | NA (0/0) | 0.0% (0/30) | 100.0% (30/30) | 90.0% (27/30) | 0.0% (0/3) | 30.0% (9/30) |
| qwen2.5:7b | 30.0% (9/30) | 100.0% (9/9) | 0.0% (0/30) | 70.0% (21/30) | 10.0% (3/30) | 0.0% (0/3) | 10.0% (3/30) | 90.0% (27/30) | 100.0% (30/30) | 0.0% (0/3) | 30.0% (9/30) |
