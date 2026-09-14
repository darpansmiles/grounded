# AdventureWorks benchmark result

- dataset: AdventureWorks
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- scoring commit: `101e056caec9863f9f14016565f1d6982e4fdbfb`
- rendered at commit: `342a324`
- capture SHA-256: `5126f0442794070b995ab018ffb68d28b0763a745750a9d6aa6dd40a89afca16`
- dataset snapshot: `datasets/adventureworks` tree `153fe7dd502deda4b904e8ed25d4504f3f2ba867`
- reproduction: `.venv/bin/python -m evals.benchmark --dataset adventureworks --runs 3 --capture-path .grounded/captures/aw-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/aw-final-r3.jsonl --recover-raw --recover-governed --offline-output .grounded/scores/aw-final-r3-review.json` (Cube must be running for governed recovery.)

Correct is conditional on answered in-catalog cases. Wrong, interface, and
evidence use all 213 in-catalog cases. Policy has 15 applicable cases.

| Model | Gov. correct | Gov. wrong | Interface | Policy | Evidence | Raw SQL correct | Raw SQL wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma2:9b | 90.5% (171/189) | 8.5% (18/213) | 100.0% (213/213) | 80.0% (12/15) | 85.9% (183/213) | 14.1% (30/213) | 85.9% (183/213) |
| llama3.1:8b | 87.3% (186/213) | 12.7% (27/213) | 100.0% (213/213) | 80.0% (12/15) | 90.1% (192/213) | 5.7% (12/210) | 93.0% (198/213) |
| llama3.2:3b | 62.9% (117/186) | 32.4% (69/213) | 90.1% (192/213) | 80.0% (12/15) | 62.0% (132/213) | 4.7% (6/129) | 57.7% (123/213) |
| mistral:7b | 58.6% (123/210) | 40.8% (87/213) | 100.0% (213/213) | 80.0% (12/15) | 78.9% (168/213) | 11.8% (12/102) | 42.3% (90/213) |
| phi3.5 | 57.4% (105/183) | 36.6% (78/213) | 100.0% (213/213) | 60.0% (9/15) | 54.9% (117/213) | 14.9% (21/141) | 56.3% (120/213) |
| phi4 | 94.3% (198/210) | 5.6% (12/213) | 100.0% (213/213) | 80.0% (12/15) | 94.4% (201/213) | 22.5% (48/213) | 77.5% (165/213) |
| qwen2.5:14b | 91.5% (195/213) | 8.5% (18/213) | 100.0% (213/213) | 80.0% (12/15) | 94.4% (201/213) | 15.5% (33/213) | 84.5% (180/213) |
| qwen2.5:3b | 0.0% (0/33) | 15.5% (33/213) | 97.2% (207/213) | 0.0% (0/15) | 7.0% (15/213) | 21.1% (24/114) | 42.3% (90/213) |
| qwen2.5:7b | 78.9% (168/213) | 21.1% (45/213) | 100.0% (213/213) | 80.0% (12/15) | 83.1% (177/213) | 17.9% (36/201) | 77.5% (165/213) |
