# BIRD california_schools benchmark result

- dataset: BIRD california_schools
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- scoring commit: `101e056caec9863f9f14016565f1d6982e4fdbfb`
- rendered at commit: `ebbcf12`
- capture SHA-256: `01faf49e6ae8eef026e3e4ba283e750222c354b15d5b0c5dc583638343f9f9dc`
- dataset snapshot: `datasets/bird_ca_schools` tree `b8534df9640928804091c94fd68a5e3f14179337`
- publication gate: unscorable governed=0, raw=0; recovery errors governed=0, raw=0
- reproduction: `.venv/bin/python -m evals.benchmark --dataset bird_ca_schools --runs 3 --capture-path .grounded/captures/bird-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/bird-final-r3.jsonl --recover-raw --recover-governed --offline-output .grounded/scores/bird-final-r3-review.json` (Cube must be running for governed recovery.)

Correct is conditional on answered in-catalog cases. Wrong, interface, and
evidence use all 69 in-catalog cases. There are no applicable policy cases.

| Model | Gov. correct | Gov. wrong | Interface | Policy | Evidence | Raw SQL correct | Raw SQL wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma2:9b | 100.0% (69/69) | 0.0% (0/69) | 100.0% (69/69) | NA (0/0) | 78.3% (54/69) | 0.0% (0/36) | 52.2% (36/69) |
| llama3.1:8b | 78.3% (54/69) | 21.7% (15/69) | 100.0% (69/69) | NA (0/0) | 56.5% (39/69) | 9.1% (3/33) | 43.5% (30/69) |
| llama3.2:3b | 60.0% (27/45) | 26.1% (18/69) | 65.2% (45/69) | NA (0/0) | 39.1% (27/69) | 0.0% (0/33) | 47.8% (33/69) |
| mistral:7b | 82.6% (57/69) | 17.4% (12/69) | 100.0% (69/69) | NA (0/0) | 69.6% (48/69) | 7.1% (3/42) | 56.5% (39/69) |
| phi3.5 | 60.9% (42/69) | 39.1% (27/69) | 100.0% (69/69) | NA (0/0) | 65.2% (45/69) | 0.0% (0/33) | 47.8% (33/69) |
| phi4 | 95.2% (60/63) | 4.3% (3/69) | 100.0% (69/69) | NA (0/0) | 65.2% (45/69) | 0.0% (0/42) | 60.9% (42/69) |
| qwen2.5:14b | 100.0% (69/69) | 0.0% (0/69) | 100.0% (69/69) | NA (0/0) | 78.3% (54/69) | 10.0% (6/60) | 78.3% (54/69) |
| qwen2.5:3b | 60.9% (42/69) | 39.1% (27/69) | 100.0% (69/69) | NA (0/0) | 65.2% (45/69) | 14.3% (3/21) | 26.1% (18/69) |
| qwen2.5:7b | 100.0% (69/69) | 0.0% (0/69) | 100.0% (69/69) | NA (0/0) | 78.3% (54/69) | 15.4% (6/39) | 47.8% (33/69) |
