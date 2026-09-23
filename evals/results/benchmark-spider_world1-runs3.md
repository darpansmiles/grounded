# Spider world_1 benchmark result

- dataset: Spider world_1
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- scoring commit: `101e056caec9863f9f14016565f1d6982e4fdbfb`
- rendered at commit: `a6a23dd`
- capture SHA-256: `5704a2c179f689e377193c13b8aaf1452bea01cbce78e98ae630669e5815348c`
- dataset snapshot: `datasets/spider_world1` tree `dc34acd23ac8f1e7133348646d4de72e37200bed`
- publication gate: unscorable governed=0, raw=0; recovery errors governed=0, raw=0
- reproduction: `.venv/bin/python -m evals.benchmark --dataset spider_world1 --runs 3 --capture-path .grounded/captures/spider-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/spider-final-r3.jsonl --recover-raw --recover-governed --offline-output .grounded/scores/spider-final-r3-review.json` (Cube must be running for governed recovery.)

Primary correctness is correct / all 93 in-catalog attempts. The
diagnostic table retains answered-case correctness, coverage, wrong, and no
scored answer. Policy has 3 applicable cases.

## Primary correctness

| Model | Attempts | Governed correct / all | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 93 | 100.0% (93/93) | 3.2% (3/93) |
| llama3.1:8b | 93 | 96.8% (90/93) | 9.7% (9/93) |
| llama3.2:3b | 93 | 74.2% (69/93) | 0.0% (0/93) |
| mistral:7b | 93 | 93.5% (87/93) | 3.2% (3/93) |
| phi3.5 | 93 | 90.3% (84/93) | 0.0% (0/93) |
| phi4 | 93 | 100.0% (93/93) | 6.5% (6/93) |
| qwen2.5:14b | 93 | 100.0% (93/93) | 3.2% (3/93) |
| qwen2.5:3b | 93 | 93.5% (87/93) | 6.5% (6/93) |
| qwen2.5:7b | 93 | 96.8% (90/93) | 12.9% (12/93) |

## Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all | Interface | Policy | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 100.0% (93/93) | 100.0% (93/93) | 0.0% (0/93) | 0.0% (0/93) | 100.0% (93/93) | 3.2% (3/93) | 96.8% (90/93) | 0.0% (0/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) |
| llama3.1:8b | 100.0% (93/93) | 96.8% (90/93) | 3.2% (3/93) | 0.0% (0/93) | 100.0% (93/93) | 9.7% (9/93) | 90.3% (84/93) | 0.0% (0/93) | 100.0% (93/93) | 100.0% (3/3) | 96.8% (90/93) |
| llama3.2:3b | 93.5% (87/93) | 79.3% (69/87) | 19.4% (18/93) | 6.5% (6/93) | 90.3% (84/93) | 0.0% (0/84) | 90.3% (84/93) | 9.7% (9/93) | 93.5% (87/93) | 100.0% (3/3) | 83.9% (78/93) |
| mistral:7b | 100.0% (93/93) | 93.5% (87/93) | 6.5% (6/93) | 0.0% (0/93) | 64.5% (60/93) | 5.0% (3/60) | 61.3% (57/93) | 35.5% (33/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) |
| phi3.5 | 96.8% (90/93) | 93.3% (84/90) | 6.5% (6/93) | 3.2% (3/93) | 61.3% (57/93) | 0.0% (0/57) | 61.3% (57/93) | 38.7% (36/93) | 100.0% (93/93) | 100.0% (3/3) | 96.8% (90/93) |
| phi4 | 100.0% (93/93) | 100.0% (93/93) | 0.0% (0/93) | 0.0% (0/93) | 100.0% (93/93) | 6.5% (6/93) | 93.5% (87/93) | 0.0% (0/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) |
| qwen2.5:14b | 100.0% (93/93) | 100.0% (93/93) | 0.0% (0/93) | 0.0% (0/93) | 100.0% (93/93) | 3.2% (3/93) | 96.8% (90/93) | 0.0% (0/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) |
| qwen2.5:3b | 100.0% (93/93) | 93.5% (87/93) | 6.5% (6/93) | 0.0% (0/93) | 83.9% (78/93) | 7.7% (6/78) | 77.4% (72/93) | 16.1% (15/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) |
| qwen2.5:7b | 100.0% (93/93) | 96.8% (90/93) | 3.2% (3/93) | 0.0% (0/93) | 96.8% (90/93) | 13.3% (12/90) | 83.9% (78/93) | 3.2% (3/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) |
