# BIRD california_schools benchmark result

- dataset: BIRD california_schools
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth

Correct is conditional on answered in-catalog cases. Wrong, interface, and
evidence use all 69 in-catalog cases. There are no applicable policy cases.

| Model | Gov. correct | Gov. wrong | Interface | Policy | Evidence | Raw SQL correct | Raw SQL wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma2:9b | 100.0% (69/69) | 0.0% (0/69) | 100.0% (69/69) | n/a | 78.3% (54/69) | 0.0% (0/36) | 52.2% (36/69) |
| llama3.1:8b | 78.3% (54/69) | 21.7% (15/69) | 100.0% (69/69) | n/a | 56.5% (39/69) | 9.1% (3/33) | 43.5% (30/69) |
| llama3.2:3b | 60.0% (27/45) | 26.1% (18/69) | 65.2% (45/69) | n/a | 39.1% (27/69) | 0.0% (0/33) | 47.8% (33/69) |
| mistral:7b | 82.6% (57/69) | 17.4% (12/69) | 100.0% (69/69) | n/a | 69.6% (48/69) | 7.1% (3/42) | 56.5% (39/69) |
| phi3.5 | 60.9% (42/69) | 39.1% (27/69) | 100.0% (69/69) | n/a | 65.2% (45/69) | 0.0% (0/33) | 47.8% (33/69) |
| phi4 | 95.2% (60/63) | 4.3% (3/69) | 100.0% (69/69) | n/a | 65.2% (45/69) | 0.0% (0/42) | 60.9% (42/69) |
| qwen2.5:14b | 100.0% (69/69) | 0.0% (0/69) | 100.0% (69/69) | n/a | 78.3% (54/69) | 10.0% (6/60) | 78.3% (54/69) |
| qwen2.5:3b | 60.9% (42/69) | 39.1% (27/69) | 100.0% (69/69) | n/a | 65.2% (45/69) | 14.3% (3/21) | 26.1% (18/69) |
| qwen2.5:7b | 100.0% (69/69) | 0.0% (0/69) | 100.0% (69/69) | n/a | 78.3% (54/69) | 15.4% (6/39) | 47.8% (33/69) |
