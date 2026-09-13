# Spider world_1 benchmark result

- dataset: Spider world_1
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- collection commit: `1f1f58a`
- scoring commit: `397555a`
- capture SHA-256: `5704a2c179f689e377193c13b8aaf1452bea01cbce78e98ae630669e5815348c`
- dataset snapshot: `datasets/spider_world1` tree `dc34acd23ac8f1e7133348646d4de72e37200bed`
- reproduction: `.venv/bin/python -m evals.benchmark --dataset spider_world1 --runs 3 --capture-path .grounded/captures/spider-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/spider-final-r3.jsonl --offline-output .grounded/scores/spider-final-r3-review-066.json`

Correct is conditional on answered in-catalog cases. Wrong, interface, and
evidence use all 93 in-catalog cases. Policy has 3 applicable cases.

| Model | Gov. correct | Gov. wrong | Interface | Policy | Evidence | Raw SQL correct | Raw SQL wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma2:9b | 100.0% (93/93) | 0.0% (0/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) | 3.2% (3/93) | 96.8% (90/93) |
| llama3.1:8b | 96.8% (90/93) | 3.2% (3/93) | 100.0% (93/93) | 100.0% (3/3) | 96.8% (90/93) | 9.7% (9/93) | 90.3% (84/93) |
| llama3.2:3b | 79.3% (69/87) | 19.4% (18/93) | 93.5% (87/93) | 100.0% (3/3) | 83.9% (78/93) | 0.0% (0/84) | 90.3% (84/93) |
| mistral:7b | 93.5% (87/93) | 6.5% (6/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) | 5.0% (3/60) | 61.3% (57/93) |
| phi3.5 | 93.3% (84/90) | 6.5% (6/93) | 100.0% (93/93) | 100.0% (3/3) | 96.8% (90/93) | 0.0% (0/57) | 61.3% (57/93) |
| phi4 | 100.0% (93/93) | 0.0% (0/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) | 6.5% (6/93) | 93.5% (87/93) |
| qwen2.5:14b | 100.0% (93/93) | 0.0% (0/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) | 3.2% (3/93) | 96.8% (90/93) |
| qwen2.5:3b | 93.5% (87/93) | 6.5% (6/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) | 7.7% (6/78) | 77.4% (72/93) |
| qwen2.5:7b | 96.8% (90/93) | 3.2% (3/93) | 100.0% (93/93) | 100.0% (3/3) | 100.0% (93/93) | 13.3% (12/90) | 83.9% (78/93) |
