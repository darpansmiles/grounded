# Benchmarks

Grounded's runs=3 evaluation is a system comparison: a catalog plus governed
tools versus a schema plus raw SQL. It does not isolate the causal contribution
of any one component.

For every non-refusal governed proposal, the evaluator executes the model's
produced declared call under the case role and compares its rows with
independently computed direct-SQL truth. The raw-SQL arm receives the same
question and schema, proposes one SQL SELECT, and is scored symmetrically.
Every score report passed an evaluator self-test that seeds a wrong metric,
wrong period, duplicate result, missing evidence, and forbidden scope.

Correct is conditional on an answered, in-catalog case. Wrong is a
valid-but-wrong answer over all in-catalog cases. The detailed result cards
also report interface compliance, policy compliance, and evidence completeness
with their applicable denominators.

All figures aggregate three runs at temperature 0. Run variance was
approximately zero. The fixture is a tiny deterministic pack with small
denominators; it validates the test surface and does not carry the product
argument.

## AdventureWorks

| Model | Governed correct / answered | Governed wrong / all | Raw SQL correct / answered | Raw SQL wrong / all |
| --- | --- | --- | --- | --- |
| gemma2:9b | 90.5% (171/189) | 8.5% (18/213) | 14.1% (30/213) | 85.9% (183/213) |
| llama3.1:8b | 87.3% (186/213) | 12.7% (27/213) | 5.7% (12/210) | 93.0% (198/213) |
| llama3.2:3b | 62.9% (117/186) | 32.4% (69/213) | 4.7% (6/129) | 57.7% (123/213) |
| mistral:7b | 58.6% (123/210) | 40.8% (87/213) | 11.8% (12/102) | 42.3% (90/213) |
| phi3.5 | 57.4% (105/183) | 36.6% (78/213) | 14.9% (21/141) | 56.3% (120/213) |
| phi4 | 94.3% (198/210) | 5.6% (12/213) | 22.5% (48/213) | 77.5% (165/213) |
| qwen2.5:14b | 91.5% (195/213) | 8.5% (18/213) | 15.5% (33/213) | 84.5% (180/213) |
| qwen2.5:3b | 0.0% (0/33) | 15.5% (33/213) | 21.1% (24/114) | 42.3% (90/213) |
| qwen2.5:7b | 78.9% (168/213) | 21.1% (45/213) | 17.9% (36/201) | 77.5% (165/213) |

## TPC-H

| Model | Governed correct / answered | Governed wrong / all | Raw SQL correct / answered | Raw SQL wrong / all |
| --- | --- | --- | --- | --- |
| gemma2:9b | 98.3% (171/174) | 1.3% (3/228) | 0.0% (0/210) | 92.1% (210/228) |
| llama3.1:8b | 92.1% (210/228) | 7.9% (18/228) | 0.0% (0/210) | 92.1% (210/228) |
| llama3.2:3b | 58.3% (105/180) | 32.9% (75/228) | 0.0% (0/105) | 46.1% (105/228) |
| mistral:7b | 50.0% (108/216) | 47.4% (108/228) | 0.0% (0/213) | 93.4% (213/228) |
| phi3.5 | 78.1% (150/192) | 18.4% (42/228) | 0.0% (0/114) | 50.0% (114/228) |
| phi4 | 98.6% (213/216) | 1.3% (3/228) | 0.0% (0/228) | 100.0% (228/228) |
| qwen2.5:14b | 98.7% (225/228) | 1.3% (3/228) | 0.0% (0/228) | 100.0% (228/228) |
| qwen2.5:3b | 10.5% (12/114) | 44.7% (102/228) | 0.0% (0/120) | 52.6% (120/228) |
| qwen2.5:7b | 93.4% (213/228) | 6.6% (15/228) | 0.0% (0/192) | 84.2% (192/228) |

## Spider world_1

| Model | Governed correct / answered | Governed wrong / all | Raw SQL correct / answered | Raw SQL wrong / all |
| --- | --- | --- | --- | --- |
| gemma2:9b | 100.0% (93/93) | 0.0% (0/93) | 3.2% (3/93) | 96.8% (90/93) |
| llama3.1:8b | 96.8% (90/93) | 3.2% (3/93) | 9.7% (9/93) | 90.3% (84/93) |
| llama3.2:3b | 79.3% (69/87) | 19.4% (18/93) | 0.0% (0/84) | 90.3% (84/93) |
| mistral:7b | 93.5% (87/93) | 6.5% (6/93) | 5.0% (3/60) | 61.3% (57/93) |
| phi3.5 | 93.3% (84/90) | 6.5% (6/93) | 0.0% (0/57) | 61.3% (57/93) |
| phi4 | 100.0% (93/93) | 0.0% (0/93) | 6.5% (6/93) | 93.5% (87/93) |
| qwen2.5:14b | 100.0% (93/93) | 0.0% (0/93) | 3.2% (3/93) | 96.8% (90/93) |
| qwen2.5:3b | 93.5% (87/93) | 6.5% (6/93) | 7.7% (6/78) | 77.4% (72/93) |
| qwen2.5:7b | 96.8% (90/93) | 3.2% (3/93) | 13.3% (12/90) | 83.9% (78/93) |

## BIRD california_schools

| Model | Governed correct / answered | Governed wrong / all | Raw SQL correct / answered | Raw SQL wrong / all |
| --- | --- | --- | --- | --- |
| gemma2:9b | 100.0% (69/69) | 0.0% (0/69) | 0.0% (0/36) | 52.2% (36/69) |
| llama3.1:8b | 78.3% (54/69) | 21.7% (15/69) | 9.1% (3/33) | 43.5% (30/69) |
| llama3.2:3b | 60.0% (27/45) | 26.1% (18/69) | 0.0% (0/33) | 47.8% (33/69) |
| mistral:7b | 82.6% (57/69) | 17.4% (12/69) | 7.1% (3/42) | 56.5% (39/69) |
| phi3.5 | 60.9% (42/69) | 39.1% (27/69) | 0.0% (0/33) | 47.8% (33/69) |
| phi4 | 95.2% (60/63) | 4.3% (3/69) | 0.0% (0/42) | 60.9% (42/69) |
| qwen2.5:14b | 100.0% (69/69) | 0.0% (0/69) | 10.0% (6/60) | 78.3% (54/69) |
| qwen2.5:3b | 60.9% (42/69) | 39.1% (27/69) | 14.3% (3/21) | 26.1% (18/69) |
| qwen2.5:7b | 100.0% (69/69) | 0.0% (0/69) | 15.4% (6/39) | 47.8% (33/69) |

## Fixture

| Model | Governed correct / answered | Governed wrong / all | Raw SQL correct / answered | Raw SQL wrong / all |
| --- | --- | --- | --- | --- |
| gemma2:9b | 100.0% (3/3) | 0.0% (0/30) | 0.0% (0/15) | 50.0% (15/30) |
| llama3.1:8b | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/15) | 50.0% (15/30) |
| llama3.2:3b | 80.0% (24/30) | 20.0% (6/30) | 0.0% (0/24) | 80.0% (24/30) |
| mistral:7b | 80.0% (24/30) | 20.0% (6/30) | 0.0% (0/12) | 40.0% (12/30) |
| phi3.5 | 100.0% (6/6) | 0.0% (0/30) | NA (0/0) | 0.0% (0/30) |
| phi4 | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/27) | 90.0% (27/30) |
| qwen2.5:14b | 100.0% (30/30) | 0.0% (0/30) | 12.5% (3/24) | 70.0% (21/30) |
| qwen2.5:3b | 100.0% (9/9) | 0.0% (0/30) | NA (0/0) | 0.0% (0/30) |
| qwen2.5:7b | 100.0% (9/9) | 0.0% (0/30) | 0.0% (0/3) | 10.0% (3/30) |

## Limits

- These results apply to the five declared packs, tested local models, prompts,
  and evaluation conditions. They do not establish universal correctness or
  production readiness.
- A governed call can be structurally valid and still answer the wrong question.
- Both arms are numerically normalized to the same two-decimal precision before
  comparison, so a raw value that is correct but differently rounded is not
  counted wrong. Under that symmetric comparison, raw-SQL correctness on
  AdventureWorks is 4.7–22.5% across the nine models (14.1–22.5% for the four
  capable ones), not near-zero; it is 0% on TPC-H. The governed advantage is a
  claim about the capable models: on AdventureWorks the weakest model,
  qwen2.5:3b, answered 0% correct under governance versus 21.1% raw.
- The diagnostic buckets for raw failures (incorrect aggregation/join, wrong
  business definition) are **heuristic** unless manually adjudicated. A sampled
  inspection of TPC-H raw failures found genuine wrong answers (for instance a
  `SUM` returning roughly double the true revenue), so genuine errors are
  present; a complete, adjudicated classification is not yet done.
- Policy compliance here is a **scoped-result check**: it verifies the returned
  rows match the expected role-scoped result. A case can therefore fail it by
  selecting the wrong metric, not only by returning an over-scoped result, and
  the denominators are small. It is not a general authorization-robustness
  claim.
- **Validation checks.** (1) *Closed.* Earlier, legacy captures whose full
  result exceeded the stored row preview were compared by a stored exact hash
  rather than a rounding-normalized one, so a large result differing from
  expected only in precision could in principle have been miscounted. Both arms
  have now been audited directly: every raw-SQL attempt and every governed call
  across all five packs (including all truncated records) was re-executed to
  recover its full result and re-scored with the declared normalized comparison.
  No label changed in either arm. The scorer now recovers and normalizes full
  results instead of using the exact-hash fallback, so the gap cannot recur.
  (2) Card provenance is printed but not yet enforced against the scoring inputs
  (scoring commit defaults to the render-time checkout; the review JSON is not
  verified to have come from the hashed capture); this is being enforced next.
  Neither check changed a published number.
