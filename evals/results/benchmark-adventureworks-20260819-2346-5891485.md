# Grounded benchmark result

- timestamp: 2026-08-19T23:46:07.114644+00:00
- git_sha: 5891485
- models: llama3.2:3b, qwen2.5:3b, qwen2.5:7b, qwen2.5:14b, llama3.1:8b, gemma2:9b, mistral:7b, phi3.5, phi4
- golden_set: golden.yml
- golden_sha: 08bad2ccce2a34c563d40d956d720b2980e544cfc31a76faf0c23fcea856915a
- runs: 3
- ollama_available: False
- ungoverned_rejection_summary: Binder Error: Ambiguous reference to table "gold.dim_product" (duplicate alias "gold.dim_product", explicitly alias one of the tables using "AS my_alias"): 3, Binder Error: Referenced column "category" not found in FROM clause!: 30, Binder Error: Referenced column "country_region" not found in FROM clause!: 3, Binder Error: Referenced column "is_completed" not found in FROM clause!: 3, Binder Error: Referenced column "product_name" not found in FROM clause!: 3, Binder Error: Referenced column "rating" not found in FROM clause!: 3, Binder Error: Referenced table "d" not found!: 9, Binder Error: Set operations can only apply to expressions with the same number of result columns: 3, Binder Error: Values list "T1" does not have a column named "list_price": 3, Binder Error: Values list "T2" does not have a column named "country_region": 12, Binder Error: Values list "T2" does not have a column named "is_completed": 3, Binder Error: Values list "T2" does not have a column named "line_total": 3, Binder Error: Values list "T2" does not have a column named "list_price": 6, Binder Error: Values list "T2" does not have a column named "territory_key": 3, Binder Error: Values list "T3" does not have a column named "category": 3, Binder Error: Values list "T3" does not have a column named "line_total": 6, Binder Error: Values list "T3" does not have a column named "order_date": 3, Binder Error: Values list "T4" does not have a column named "country_region": 3, Binder Error: Values list "c" does not have a column named "category": 9, Binder Error: Values list "d" does not have a column named "category": 21, Binder Error: Values list "d" does not have a column named "country_region": 9, Binder Error: Values list "fct_sales" does not have a column named "list_price": 3, Binder Error: Values list "p" does not have a column named "quantity": 3, Binder Error: Values list "s" does not have a column named "repsalespersonkey": 3, Catalog Error: Table with name dim_employee does not exist!: 6, Catalog Error: Table with name dim_employees does not exist!: 3, Catalog Error: Table with name dim_supplier does not exist!: 6, Catalog Error: Table with name fct_returns does not exist!: 3, Parser Error: syntax error at or near "ORDINALITY": 3, only one SELECT statement is allowed: 87
- dataset: adventureworks
- cube_on: True

## Governed vs. ungoverned comparison

| metric | llama3.2:3b · governed | llama3.2:3b · ungoverned | qwen2.5:3b · governed | qwen2.5:3b · ungoverned | qwen2.5:7b · governed | qwen2.5:7b · ungoverned | qwen2.5:14b · governed | qwen2.5:14b · ungoverned | llama3.1:8b · governed | llama3.1:8b · ungoverned | gemma2:9b · governed | gemma2:9b · ungoverned | mistral:7b · governed | mistral:7b · ungoverned | phi3.5 · governed | phi3.5 · ungoverned | phi4 · governed | phi4 · ungoverned |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| status | completed | completed | completed | completed | completed | completed | skipped | skipped | completed | completed | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| correct_answer_rate | 58.9% | 0.0% | 5.6% | 0.0% | 73.3% | 0.0% | skipped | skipped | 71.1% | 0.0% | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| correct_refusal_rate | 17.8% | 0.0% | 25.6% | 0.0% | 23.3% | 0.0% | skipped | skipped | 12.2% | 0.0% | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| hallucination_rate | 0.0% | 72.2% | 0.0% | 52.2% | 0.0% | 92.2% | skipped | skipped | 0.0% | 87.8% | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| over_refusal_rate | 23.3% | 0.0% | 68.9% | 0.0% | 3.3% | 0.0% | skipped | skipped | 16.7% | 0.0% | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| schema_break_rate | 0.0% | 27.8% | 0.0% | 47.8% | 0.0% | 7.8% | skipped | skipped | 0.0% | 12.2% | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| routing_accuracy | 79.0% | n/a | 19.8% | n/a | 96.3% | n/a | skipped | skipped | 96.3% | n/a | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| answer_correctness_when_answered | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | skipped | skipped | 100.0% | 0.0% | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |

## Statistical summary

- llama3.2:3b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 72.2% [67.0%, 77.4%]; McNemar exact b=195, c=0, p=3.98273e-59; routing run variance=0.
- qwen2.5:3b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 52.2% [46.3%, 58.1%]; McNemar exact b=141, c=0, p=7.17465e-43; routing run variance=0.
- qwen2.5:7b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 92.2% [88.9%, 95.2%]; McNemar exact b=249, c=0, p=2.21086e-75; routing run variance=0.
- llama3.1:8b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 87.8% [83.7%, 91.5%]; McNemar exact b=237, c=0, p=9.05568e-72; routing run variance=0.

## Timing and resources

- sweep: started 2026-08-19T18:49:23.902015+00:00; ended 2026-08-19T21:47:13.784032+00:00; duration 7973.993s.
- llama3.2:3b: duration 193.419s; CPU mean 4.7%; RSS mean 84.5 MB, peak 128.3 MB.
- qwen2.5:3b: duration 281.212s; CPU mean 3.2%; RSS mean 52.4 MB, peak 55.0 MB.
- qwen2.5:7b: duration 618.557s; CPU mean 1.1%; RSS mean 53.7 MB, peak 54.1 MB.
- llama3.1:8b: duration 870.969s; CPU mean 0.8%; RSS mean 23.7 MB, peak 24.1 MB.
- gemma2:9b: duration 628.912s; CPU mean 0.5%; RSS mean 24.3 MB, peak 24.5 MB.
- mistral:7b: duration 472.074s; CPU mean 0.6%; RSS mean 24.9 MB, peak 25.0 MB.
- phi3.5: duration 893.390s; CPU mean 0.3%; RSS mean 25.0 MB, peak 25.3 MB.
