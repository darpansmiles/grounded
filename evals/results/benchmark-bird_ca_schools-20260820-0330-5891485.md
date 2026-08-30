# Grounded benchmark result

- timestamp: 2026-08-20T03:30:34.875977+00:00
- git_sha: 5891485
- models: llama3.2:3b, qwen2.5:3b, qwen2.5:7b, qwen2.5:14b, llama3.1:8b, gemma2:9b, mistral:7b, phi3.5, phi4
- golden_set: golden.yml
- golden_sha: d889916f9d4d02ef6b764704973b9342a115384763eceb1f20ede2f23d9bf4e8
- runs: 3
- ollama_available: False
- ungoverned_rejection_summary: Binder Error: Ambiguous reference to column name "CDSCode" (use: "T1.CDSCode" or "T2.CDSCode"): 3, Binder Error: Catalog "bronze" does not exist!: 6, Binder Error: No function matches the given name and argument types 'avg(VARCHAR)'. You might need to add explicit type casts.: 3, Binder Error: Referenced column "AcademicYear" not found in FROM clause!: 6, Binder Error: Referenced column "County" not found in FROM clause!: 39, Binder Error: Referenced column "CountyName" not found in FROM clause!: 27, Binder Error: Referenced column "Enrollment" not found in FROM clause!: 3, Binder Error: Referenced column "SchoolName" not found in FROM clause!: 6, Binder Error: Referenced column "School_Name" not found in FROM clause!: 3, Binder Error: Referenced column "TeacherSalary" not found in FROM clause!: 3, Binder Error: Referenced table "s" not found!: 3, Binder Error: Table "T1" does not have a column named "County": 3, Binder Error: Table "T1" does not have a column named "SchoolName": 3, Binder Error: Table "T1" does not have a column named "cname": 3, Binder Error: Table "T2" does not have a column named "FundingType": 3, Binder Error: Table "T2" does not have a column named "county_name": 3, Binder Error: Table "a" does not have a column named "AvgScrMath": 3, Binder Error: Table "a" does not have a column named "enroll12": 3, Binder Error: Table "c" does not have a column named "CountyName": 3, Binder Error: Table "frpm" does not have a column named "School_Code": 3, Binder Error: Table "s" does not have a column named "DistrictCode": 3, Binder Error: Table "s" does not have a column named "SchoolName": 3, Binder Error: Table "s" does not have a column named "cname": 3, Binder Error: Values list "b" does not have a column named "School": 3, Catalog Error: Scalar Function with name enrollment does not exist!: 30, Catalog Error: Table with name bird_ca_schools does not exist!: 3, Catalog Error: Table with name bronze does not exist!: 12, Catalog Error: Table with name districts does not exist!: 3, Catalog Error: Table with name employees does not exist!: 3, Catalog Error: Table with name teachers does not exist!: 3, Conversion Error: Could not convert string 'P' to INT32 when casting from source column Virtual: 3, Parser Error: syntax error at or near "%": 3, Parser Error: syntax error at or near "5": 3, Parser Error: syntax error at or near "CALPADS": 6, Parser Error: syntax error at or near "Code": 21, Parser Error: syntax error at or near "Count": 9, Parser Error: syntax error at or near "Enrollment": 3, Parser Error: syntax error at or near "Meal": 3, Parser Error: syntax error at or near "Name": 57, Parser Error: syntax error at or near "Year": 3, only one SELECT statement is allowed: 87
- dataset: bird_ca_schools
- cube_on: True

## Governed vs. ungoverned comparison

| metric | llama3.2:3b · governed | llama3.2:3b · ungoverned | qwen2.5:3b · governed | qwen2.5:3b · ungoverned | qwen2.5:7b · governed | qwen2.5:7b · ungoverned | qwen2.5:14b · governed | qwen2.5:14b · ungoverned | llama3.1:8b · governed | llama3.1:8b · ungoverned | gemma2:9b · governed | gemma2:9b · ungoverned | mistral:7b · governed | mistral:7b · ungoverned | phi3.5 · governed | phi3.5 · ungoverned | phi4 · governed | phi4 · ungoverned |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| status | completed | completed | completed | completed | completed | completed | completed | completed | completed | completed | completed | completed | completed | completed | completed | completed | skipped | skipped |
| correct_answer_rate | 38.9% | 0.0% | 41.7% | 5.6% | 63.9% | 2.8% | 63.9% | 0.0% | 50.0% | 5.6% | 63.9% | 0.0% | 58.3% | 0.0% | 41.7% | 2.8% | skipped | skipped |
| correct_refusal_rate | 19.4% | 0.0% | 36.1% | 0.0% | 33.3% | 0.0% | 33.3% | 0.0% | 13.9% | 0.0% | 27.8% | 0.0% | 8.3% | 0.0% | 8.3% | 0.0% | skipped | skipped |
| hallucination_rate | 0.0% | 55.6% | 0.0% | 38.9% | 0.0% | 61.1% | 0.0% | 72.2% | 0.0% | 47.2% | 0.0% | 63.9% | 0.0% | 47.2% | 0.0% | 33.3% | skipped | skipped |
| over_refusal_rate | 41.7% | 0.0% | 22.2% | 0.0% | 2.8% | 0.0% | 2.8% | 0.0% | 36.1% | 0.0% | 8.3% | 0.0% | 33.3% | 0.0% | 50.0% | 0.0% | skipped | skipped |
| schema_break_rate | 0.0% | 44.4% | 0.0% | 55.6% | 0.0% | 36.1% | 0.0% | 27.8% | 0.0% | 47.2% | 0.0% | 36.1% | 0.0% | 52.8% | 0.0% | 63.9% | skipped | skipped |
| routing_accuracy | 65.6% | n/a | 68.8% | n/a | 96.9% | n/a | 100.0% | n/a | 81.2% | n/a | 100.0% | n/a | 93.8% | n/a | 68.8% | n/a | skipped | skipped |
| answer_correctness_when_answered | 100.0% | 0.0% | 100.0% | 28.6% | 100.0% | 6.7% | 100.0% | 0.0% | 100.0% | 18.2% | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 8.3% | skipped | skipped |

## Statistical summary

- llama3.2:3b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 55.6% [46.3%, 64.8%]; McNemar exact b=60, c=0, p=1.73472e-18; routing run variance=0.
- qwen2.5:3b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 38.9% [29.6%, 48.1%]; McNemar exact b=42, c=0, p=4.54747e-13; routing run variance=0.
- qwen2.5:7b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 61.1% [51.9%, 70.4%]; McNemar exact b=66, c=0, p=2.71051e-20; routing run variance=0.
- qwen2.5:14b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 72.2% [63.0%, 80.6%]; McNemar exact b=78, c=0, p=6.61744e-24; routing run variance=0.
- llama3.1:8b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 47.2% [38.0%, 56.5%]; McNemar exact b=51, c=0, p=8.88178e-16; routing run variance=0.
- gemma2:9b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 63.9% [54.6%, 73.1%]; McNemar exact b=69, c=0, p=3.38813e-21; routing run variance=0.
- mistral:7b: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 47.2% [38.0%, 56.5%]; McNemar exact b=51, c=0, p=8.88178e-16; routing run variance=0.
- phi3.5: governed hallucination 0.0% [0.0%, 0.0%]; ungoverned hallucination 33.3% [25.0%, 42.6%]; McNemar exact b=36, c=0, p=2.91038e-11; routing run variance=0.

## Timing and resources

- sweep: started 2026-08-19T23:46:27.850690+00:00; ended 2026-08-20T01:08:53.590257+00:00; duration 4045.703s.
- llama3.2:3b: duration 132.927s; CPU mean 1.9%; RSS mean 120.0 MB, peak 120.0 MB.
- qwen2.5:3b: duration 137.487s; CPU mean 1.5%; RSS mean 60.6 MB, peak 120.0 MB.
- qwen2.5:7b: duration 255.069s; CPU mean 0.7%; RSS mean 54.0 MB, peak 54.3 MB.
- qwen2.5:14b: duration 479.404s; CPU mean 0.4%; RSS mean 54.2 MB, peak 54.5 MB.
- llama3.1:8b: duration 345.762s; CPU mean 0.5%; RSS mean 54.7 MB, peak 54.9 MB.
- gemma2:9b: duration 712.115s; CPU mean 0.3%; RSS mean 54.4 MB, peak 55.0 MB.
- mistral:7b: duration 555.705s; CPU mean 0.4%; RSS mean 55.0 MB, peak 55.2 MB.
- phi3.5: duration 1012.313s; CPU mean 0.2%; RSS mean 55.7 MB, peak 56.0 MB.
- phi4: duration 414.599s; CPU mean 0.2%; RSS mean 56.1 MB, peak 56.1 MB.
