# Fixture benchmark result

- dataset: fixture
- runs: 3
- evaluator self-test: passed
- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth

This deterministic pack has 30 in-catalog cases per model. Its small
denominators make it a harness test surface, not a workload claim. Correct is
conditional on answered in-catalog cases; policy has 3 applicable cases.

| Model | Gov. correct | Gov. wrong | Interface | Policy | Evidence | Raw SQL correct | Raw SQL wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma2:9b | 0.0% (0/3) | 10.0% (3/30) | 100.0% (30/30) | 0.0% (0/3) | 10.0% (3/30) | 0.0% (0/15) | 50.0% (15/30) |
| llama3.1:8b | 90.0% (27/30) | 10.0% (3/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 0.0% (0/15) | 50.0% (15/30) |
| llama3.2:3b | 70.0% (21/30) | 30.0% (9/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 0.0% (0/24) | 80.0% (24/30) |
| mistral:7b | 70.0% (21/30) | 30.0% (9/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 0.0% (0/12) | 40.0% (12/30) |
| phi3.5 | 50.0% (3/6) | 10.0% (3/30) | 100.0% (30/30) | 0.0% (0/3) | 20.0% (6/30) | n/a | 0.0% (0/30) |
| phi4 | 90.0% (27/30) | 10.0% (3/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 0.0% (0/27) | 90.0% (27/30) |
| qwen2.5:14b | 90.0% (27/30) | 10.0% (3/30) | 100.0% (30/30) | 100.0% (3/3) | 100.0% (30/30) | 0.0% (0/24) | 80.0% (24/30) |
| qwen2.5:3b | 100.0% (9/9) | 0.0% (0/30) | 90.0% (27/30) | 0.0% (0/3) | 30.0% (9/30) | n/a | 0.0% (0/30) |
| qwen2.5:7b | 66.7% (6/9) | 10.0% (3/30) | 100.0% (30/30) | 0.0% (0/3) | 30.0% (9/30) | 0.0% (0/3) | 10.0% (3/30) |
