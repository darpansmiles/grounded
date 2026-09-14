# TPC-H benchmark result

- dataset: TPC-H
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- scoring commit: `101e056caec9863f9f14016565f1d6982e4fdbfb`
- rendered at commit: `342a324`
- capture SHA-256: `d4c7214083533d814bd3520b648bbda62e7548d2a0fc928def8874a8a1166f7c`
- dataset snapshot: `datasets/tpch` tree `fabff8c205022175d782236415aed1e64a46184c`
- reproduction: `.venv/bin/python -m evals.benchmark --dataset tpch --runs 3 --capture-path .grounded/captures/tpch-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/tpch-final-r3.jsonl --recover-raw --recover-governed --offline-output .grounded/scores/tpch-final-r3-review.json` (Cube must be running for governed recovery.)

Correct is conditional on answered in-catalog cases. Wrong, interface, and
evidence use all 228 in-catalog cases. Policy has 3 applicable cases.

| Model | Gov. correct | Gov. wrong | Interface | Policy | Evidence | Raw SQL correct | Raw SQL wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma2:9b | 98.3% (171/174) | 1.3% (3/228) | 100.0% (228/228) | 100.0% (3/3) | 75.0% (171/228) | 0.0% (0/210) | 92.1% (210/228) |
| llama3.1:8b | 92.1% (210/228) | 7.9% (18/228) | 100.0% (228/228) | 100.0% (3/3) | 92.1% (210/228) | 0.0% (0/210) | 92.1% (210/228) |
| llama3.2:3b | 58.3% (105/180) | 32.9% (75/228) | 89.5% (204/228) | 100.0% (3/3) | 69.7% (159/228) | 0.0% (0/105) | 46.1% (105/228) |
| mistral:7b | 50.0% (108/216) | 47.4% (108/228) | 98.7% (225/228) | 0.0% (0/3) | 80.3% (183/228) | 0.0% (0/213) | 93.4% (213/228) |
| phi3.5 | 78.1% (150/192) | 18.4% (42/228) | 100.0% (228/228) | 100.0% (3/3) | 71.1% (162/228) | 0.0% (0/114) | 50.0% (114/228) |
| phi4 | 98.6% (213/216) | 1.3% (3/228) | 100.0% (228/228) | 100.0% (3/3) | 93.4% (213/228) | 0.0% (0/228) | 100.0% (228/228) |
| qwen2.5:14b | 98.7% (225/228) | 1.3% (3/228) | 100.0% (228/228) | 100.0% (3/3) | 98.7% (225/228) | 0.0% (0/228) | 100.0% (228/228) |
| qwen2.5:3b | 10.5% (12/114) | 44.7% (102/228) | 94.7% (216/228) | 0.0% (0/3) | 50.0% (114/228) | 0.0% (0/120) | 52.6% (120/228) |
| qwen2.5:7b | 93.4% (213/228) | 6.6% (15/228) | 100.0% (228/228) | 100.0% (3/3) | 93.4% (213/228) | 0.0% (0/192) | 84.2% (192/228) |
