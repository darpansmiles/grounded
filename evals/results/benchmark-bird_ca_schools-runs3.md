# BIRD california_schools benchmark result

- dataset: BIRD california_schools
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth
- scoring commit: `101e056caec9863f9f14016565f1d6982e4fdbfb`
- rendered at commit: `a6a23dd`
- capture SHA-256: `01faf49e6ae8eef026e3e4ba283e750222c354b15d5b0c5dc583638343f9f9dc`
- dataset snapshot: `datasets/bird_ca_schools` tree `b8534df9640928804091c94fd68a5e3f14179337`
- publication gate: unscorable governed=0, raw=0; recovery errors governed=0, raw=0
- reproduction: `.venv/bin/python -m evals.benchmark --dataset bird_ca_schools --runs 3 --capture-path .grounded/captures/bird-final-r3.jsonl && .venv/bin/python -m evals.compare --capture-path .grounded/captures/bird-final-r3.jsonl --recover-raw --recover-governed --offline-output .grounded/scores/bird-final-r3-review.json` (Cube must be running for governed recovery.)

Primary correctness is correct / all 69 in-catalog attempts. The
diagnostic table retains answered-case correctness, coverage, wrong, and no
scored answer. There are no applicable policy cases.

## Primary correctness

| Model | Attempts | Governed correct / all | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 69 | 100.0% (69/69) | 0.0% (0/69) |
| llama3.1:8b | 69 | 78.3% (54/69) | 4.3% (3/69) |
| llama3.2:3b | 69 | 39.1% (27/69) | 0.0% (0/69) |
| mistral:7b | 69 | 82.6% (57/69) | 4.3% (3/69) |
| phi3.5 | 69 | 60.9% (42/69) | 0.0% (0/69) |
| phi4 | 69 | 87.0% (60/69) | 0.0% (0/69) |
| qwen2.5:14b | 69 | 100.0% (69/69) | 8.7% (6/69) |
| qwen2.5:3b | 69 | 60.9% (42/69) | 4.3% (3/69) |
| qwen2.5:7b | 69 | 100.0% (69/69) | 8.7% (6/69) |

## Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all | Interface | Policy | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 100.0% (69/69) | 100.0% (69/69) | 0.0% (0/69) | 0.0% (0/69) | 52.2% (36/69) | 0.0% (0/36) | 52.2% (36/69) | 47.8% (33/69) | 100.0% (69/69) | NA (0/0) | 78.3% (54/69) |
| llama3.1:8b | 100.0% (69/69) | 78.3% (54/69) | 21.7% (15/69) | 0.0% (0/69) | 47.8% (33/69) | 9.1% (3/33) | 43.5% (30/69) | 52.2% (36/69) | 100.0% (69/69) | NA (0/0) | 56.5% (39/69) |
| llama3.2:3b | 65.2% (45/69) | 60.0% (27/45) | 26.1% (18/69) | 34.8% (24/69) | 47.8% (33/69) | 0.0% (0/33) | 47.8% (33/69) | 52.2% (36/69) | 65.2% (45/69) | NA (0/0) | 39.1% (27/69) |
| mistral:7b | 100.0% (69/69) | 82.6% (57/69) | 17.4% (12/69) | 0.0% (0/69) | 60.9% (42/69) | 7.1% (3/42) | 56.5% (39/69) | 39.1% (27/69) | 100.0% (69/69) | NA (0/0) | 69.6% (48/69) |
| phi3.5 | 100.0% (69/69) | 60.9% (42/69) | 39.1% (27/69) | 0.0% (0/69) | 47.8% (33/69) | 0.0% (0/33) | 47.8% (33/69) | 52.2% (36/69) | 100.0% (69/69) | NA (0/0) | 65.2% (45/69) |
| phi4 | 91.3% (63/69) | 95.2% (60/63) | 4.3% (3/69) | 8.7% (6/69) | 60.9% (42/69) | 0.0% (0/42) | 60.9% (42/69) | 39.1% (27/69) | 100.0% (69/69) | NA (0/0) | 65.2% (45/69) |
| qwen2.5:14b | 100.0% (69/69) | 100.0% (69/69) | 0.0% (0/69) | 0.0% (0/69) | 87.0% (60/69) | 10.0% (6/60) | 78.3% (54/69) | 13.0% (9/69) | 100.0% (69/69) | NA (0/0) | 78.3% (54/69) |
| qwen2.5:3b | 100.0% (69/69) | 60.9% (42/69) | 39.1% (27/69) | 0.0% (0/69) | 30.4% (21/69) | 14.3% (3/21) | 26.1% (18/69) | 69.6% (48/69) | 100.0% (69/69) | NA (0/0) | 65.2% (45/69) |
| qwen2.5:7b | 100.0% (69/69) | 100.0% (69/69) | 0.0% (0/69) | 0.0% (0/69) | 56.5% (39/69) | 15.4% (6/39) | 47.8% (33/69) | 43.5% (30/69) | 100.0% (69/69) | NA (0/0) | 78.3% (54/69) |
