# TPC-H benchmark result

- dataset: TPC-H
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- scoring commit: `101e056caec9863f9f14016565f1d6982e4fdbfb`
- rendered at commit: `a6a23dd`
- capture SHA-256: `d4c7214083533d814bd3520b648bbda62e7548d2a0fc928def8874a8a1166f7c`
- dataset snapshot: `datasets/tpch` tree `fabff8c205022175d782236415aed1e64a46184c`
- publication gate: unscorable governed=0, raw=0; recovery errors governed=0, raw=0
- reproduction: `.venv/bin/python -m evals.benchmark --dataset tpch --runs 3 --capture-path .grounded/captures/tpch-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/tpch-final-r3.jsonl --recover-raw --recover-governed --offline-output .grounded/scores/tpch-final-r3-review.json` (Cube must be running for governed recovery.)

Primary correctness is correct / all 228 in-catalog attempts. The
diagnostic table retains answered-case correctness, coverage, wrong, and no
scored answer. Policy has 3 applicable cases.

## Primary correctness

| Model | Attempts | Governed correct / all | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 228 | 75.0% (171/228) | 0.0% (0/228) |
| llama3.1:8b | 228 | 92.1% (210/228) | 0.0% (0/228) |
| llama3.2:3b | 228 | 46.1% (105/228) | 0.0% (0/228) |
| mistral:7b | 228 | 47.4% (108/228) | 0.0% (0/228) |
| phi3.5 | 228 | 65.8% (150/228) | 0.0% (0/228) |
| phi4 | 228 | 93.4% (213/228) | 0.0% (0/228) |
| qwen2.5:14b | 228 | 98.7% (225/228) | 0.0% (0/228) |
| qwen2.5:3b | 228 | 5.3% (12/228) | 0.0% (0/228) |
| qwen2.5:7b | 228 | 93.4% (213/228) | 0.0% (0/228) |

## Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all | Interface | Policy | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 76.3% (174/228) | 98.3% (171/174) | 1.3% (3/228) | 23.7% (54/228) | 92.1% (210/228) | 0.0% (0/210) | 92.1% (210/228) | 7.9% (18/228) | 100.0% (228/228) | 100.0% (3/3) | 75.0% (171/228) |
| llama3.1:8b | 100.0% (228/228) | 92.1% (210/228) | 7.9% (18/228) | 0.0% (0/228) | 92.1% (210/228) | 0.0% (0/210) | 92.1% (210/228) | 7.9% (18/228) | 100.0% (228/228) | 100.0% (3/3) | 92.1% (210/228) |
| llama3.2:3b | 78.9% (180/228) | 58.3% (105/180) | 32.9% (75/228) | 21.1% (48/228) | 46.1% (105/228) | 0.0% (0/105) | 46.1% (105/228) | 53.9% (123/228) | 89.5% (204/228) | 100.0% (3/3) | 69.7% (159/228) |
| mistral:7b | 94.7% (216/228) | 50.0% (108/216) | 47.4% (108/228) | 5.3% (12/228) | 93.4% (213/228) | 0.0% (0/213) | 93.4% (213/228) | 6.6% (15/228) | 98.7% (225/228) | 0.0% (0/3) | 80.3% (183/228) |
| phi3.5 | 84.2% (192/228) | 78.1% (150/192) | 18.4% (42/228) | 15.8% (36/228) | 50.0% (114/228) | 0.0% (0/114) | 50.0% (114/228) | 50.0% (114/228) | 100.0% (228/228) | 100.0% (3/3) | 71.1% (162/228) |
| phi4 | 94.7% (216/228) | 98.6% (213/216) | 1.3% (3/228) | 5.3% (12/228) | 100.0% (228/228) | 0.0% (0/228) | 100.0% (228/228) | 0.0% (0/228) | 100.0% (228/228) | 100.0% (3/3) | 93.4% (213/228) |
| qwen2.5:14b | 100.0% (228/228) | 98.7% (225/228) | 1.3% (3/228) | 0.0% (0/228) | 100.0% (228/228) | 0.0% (0/228) | 100.0% (228/228) | 0.0% (0/228) | 100.0% (228/228) | 100.0% (3/3) | 98.7% (225/228) |
| qwen2.5:3b | 50.0% (114/228) | 10.5% (12/114) | 44.7% (102/228) | 50.0% (114/228) | 52.6% (120/228) | 0.0% (0/120) | 52.6% (120/228) | 47.4% (108/228) | 94.7% (216/228) | 0.0% (0/3) | 50.0% (114/228) |
| qwen2.5:7b | 100.0% (228/228) | 93.4% (213/228) | 6.6% (15/228) | 0.0% (0/228) | 84.2% (192/228) | 0.0% (0/192) | 84.2% (192/228) | 15.8% (36/228) | 100.0% (228/228) | 100.0% (3/3) | 93.4% (213/228) |
