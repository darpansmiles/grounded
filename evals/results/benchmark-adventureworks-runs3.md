# AdventureWorks benchmark result

- dataset: AdventureWorks
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- scoring commit: `101e056caec9863f9f14016565f1d6982e4fdbfb`
- rendered at commit: `a6a23dd`
- capture SHA-256: `5126f0442794070b995ab018ffb68d28b0763a745750a9d6aa6dd40a89afca16`
- dataset snapshot: `datasets/adventureworks` tree `153fe7dd502deda4b904e8ed25d4504f3f2ba867`
- publication gate: unscorable governed=0, raw=0; recovery errors governed=0, raw=0
- reproduction: `.venv/bin/python -m evals.benchmark --dataset adventureworks --runs 3 --capture-path .grounded/captures/aw-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/aw-final-r3.jsonl --recover-raw --recover-governed --offline-output .grounded/scores/aw-final-r3-review.json` (Cube must be running for governed recovery.)

Primary correctness is correct / all 213 in-catalog attempts. The
diagnostic table retains answered-case correctness, coverage, wrong, and no
scored answer. Policy has 15 applicable cases.

## Primary correctness

| Model | Attempts | Governed correct / all | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 213 | 80.3% (171/213) | 14.1% (30/213) |
| llama3.1:8b | 213 | 87.3% (186/213) | 5.6% (12/213) |
| llama3.2:3b | 213 | 54.9% (117/213) | 2.8% (6/213) |
| mistral:7b | 213 | 57.7% (123/213) | 5.6% (12/213) |
| phi3.5 | 213 | 49.3% (105/213) | 9.9% (21/213) |
| phi4 | 213 | 93.0% (198/213) | 22.5% (48/213) |
| qwen2.5:14b | 213 | 91.5% (195/213) | 15.5% (33/213) |
| qwen2.5:3b | 213 | 0.0% (0/213) | 11.3% (24/213) |
| qwen2.5:7b | 213 | 78.9% (168/213) | 16.9% (36/213) |

## Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all | Interface | Policy | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 88.7% (189/213) | 90.5% (171/189) | 8.5% (18/213) | 11.3% (24/213) | 100.0% (213/213) | 14.1% (30/213) | 85.9% (183/213) | 0.0% (0/213) | 100.0% (213/213) | 80.0% (12/15) | 85.9% (183/213) |
| llama3.1:8b | 100.0% (213/213) | 87.3% (186/213) | 12.7% (27/213) | 0.0% (0/213) | 98.6% (210/213) | 5.7% (12/210) | 93.0% (198/213) | 1.4% (3/213) | 100.0% (213/213) | 80.0% (12/15) | 90.1% (192/213) |
| llama3.2:3b | 87.3% (186/213) | 62.9% (117/186) | 32.4% (69/213) | 12.7% (27/213) | 60.6% (129/213) | 4.7% (6/129) | 57.7% (123/213) | 39.4% (84/213) | 90.1% (192/213) | 80.0% (12/15) | 62.0% (132/213) |
| mistral:7b | 98.6% (210/213) | 58.6% (123/210) | 40.8% (87/213) | 1.4% (3/213) | 47.9% (102/213) | 11.8% (12/102) | 42.3% (90/213) | 52.1% (111/213) | 100.0% (213/213) | 80.0% (12/15) | 78.9% (168/213) |
| phi3.5 | 85.9% (183/213) | 57.4% (105/183) | 36.6% (78/213) | 14.1% (30/213) | 66.2% (141/213) | 14.9% (21/141) | 56.3% (120/213) | 33.8% (72/213) | 100.0% (213/213) | 60.0% (9/15) | 54.9% (117/213) |
| phi4 | 98.6% (210/213) | 94.3% (198/210) | 5.6% (12/213) | 1.4% (3/213) | 100.0% (213/213) | 22.5% (48/213) | 77.5% (165/213) | 0.0% (0/213) | 100.0% (213/213) | 80.0% (12/15) | 94.4% (201/213) |
| qwen2.5:14b | 100.0% (213/213) | 91.5% (195/213) | 8.5% (18/213) | 0.0% (0/213) | 100.0% (213/213) | 15.5% (33/213) | 84.5% (180/213) | 0.0% (0/213) | 100.0% (213/213) | 80.0% (12/15) | 94.4% (201/213) |
| qwen2.5:3b | 15.5% (33/213) | 0.0% (0/33) | 15.5% (33/213) | 84.5% (180/213) | 53.5% (114/213) | 21.1% (24/114) | 42.3% (90/213) | 46.5% (99/213) | 97.2% (207/213) | 0.0% (0/15) | 7.0% (15/213) |
| qwen2.5:7b | 100.0% (213/213) | 78.9% (168/213) | 21.1% (45/213) | 0.0% (0/213) | 94.4% (201/213) | 17.9% (36/201) | 77.5% (165/213) | 5.6% (12/213) | 100.0% (213/213) | 80.0% (12/15) | 83.1% (177/213) |
