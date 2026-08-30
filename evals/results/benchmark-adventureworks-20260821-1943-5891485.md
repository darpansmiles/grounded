# Grounded benchmark result

- timestamp: 2026-08-21T19:43:56.255289+00:00
- git_sha: 5891485
- models: qwen2.5:14b, gemma2:9b, mistral:7b, phi3.5
- golden_set: golden.yml
- golden_sha: 08bad2ccce2a34c563d40d956d720b2980e544cfc31a76faf0c23fcea856915a
- runs: 3
- ollama_available: False
- ungoverned_rejection_summary: Binder Error: Referenced column "DAY" not found in FROM clause!: 3, Binder Error: Referenced table "d" not found!: 3, Binder Error: Values list "c" does not have a column named "territory_key": 3, Binder Error: Values list "p" does not have a column named "customer_id": 3, Binder Error: Values list "s" does not have a column named "shipped_date": 3, Catalog Error: Table with name customer_feedback does not exist!: 3
- dataset: adventureworks
- cube_on: True

## Governed vs. ungoverned comparison

| metric | qwen2.5:14b · governed | qwen2.5:14b · ungoverned | gemma2:9b · governed | gemma2:9b · ungoverned | mistral:7b · governed | mistral:7b · ungoverned | phi3.5 · governed | phi3.5 · ungoverned |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| status | completed | completed | completed | completed | skipped | skipped | skipped | skipped |
| correct_answer_rate | 73.3% | 0.0% | 67.8% | 0.0% | skipped | skipped | skipped | skipped |
| correct_refusal_rate | 25.6% | 0.0% | 20.0% | 0.0% | skipped | skipped | skipped | skipped |
| hallucination_rate | 0.0% | 95.6% | 0.0% | 97.8% | skipped | skipped | skipped | skipped |
| over_refusal_rate | 1.1% | 0.0% | 12.2% | 0.0% | skipped | skipped | skipped | skipped |
| schema_break_rate | 0.0% | 4.4% | 0.0% | 2.2% | skipped | skipped | skipped | skipped |
| routing_accuracy | 100.0% | n/a | 93.8% | n/a | skipped | skipped | skipped | skipped |
| answer_correctness_when_answered | 100.0% | 0.0% | 100.0% | 0.0% | skipped | skipped | skipped | skipped |

## Statistical summary

- qwen2.5:14b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 95.6% [93.0%, 97.8%]; McNemar exact b=258, c=0, p=4.31808e-78; routing run variance=0.
- gemma2:9b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 97.8% [95.9%, 99.3%]; McNemar exact b=264, c=0, p=6.74701e-80; routing run variance=1.2326e-32.

## Timing and resources

- sweep: started 2026-08-21T17:27:11.816525+00:00; ended 2026-08-21T18:32:10.526634+00:00; duration 3898.694s.
- qwen2.5:14b: duration 636.297s; CPU mean 1.0%; RSS mean 48.3 MB, peak 128.2 MB.
- gemma2:9b: duration 1462.759s; CPU mean 0.5%; RSS mean 27.9 MB, peak 48.5 MB.
- phi3.5: duration 715.929s; CPU mean 0.4%; RSS mean 18.1 MB, peak 21.2 MB.
