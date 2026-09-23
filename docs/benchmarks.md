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

Primary correctness is **correct / all in-catalog attempts**, with one
denominator for every model and both arms. Refusals and failed attempts receive
no correctness credit. Coverage and correct when answered are reported in the
diagnostic table to expose the answer-more-versus-answer-accurately tradeoff.
Counts aggregate three runs and are attempts, not distinct questions.

All figures aggregate three runs at temperature 0. Run variance was
approximately zero. The fixture is a tiny deterministic pack with small
denominators; it validates the test surface and does not carry the product
argument.

## AdventureWorks

### Primary correctness

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

### Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 88.7% (189/213) | 90.5% (171/189) | 8.5% (18/213) | 11.3% (24/213) | 100.0% (213/213) | 14.1% (30/213) | 85.9% (183/213) | 0.0% (0/213) |
| llama3.1:8b | 100.0% (213/213) | 87.3% (186/213) | 12.7% (27/213) | 0.0% (0/213) | 98.6% (210/213) | 5.7% (12/210) | 93.0% (198/213) | 1.4% (3/213) |
| llama3.2:3b | 87.3% (186/213) | 62.9% (117/186) | 32.4% (69/213) | 12.7% (27/213) | 60.6% (129/213) | 4.7% (6/129) | 57.7% (123/213) | 39.4% (84/213) |
| mistral:7b | 98.6% (210/213) | 58.6% (123/210) | 40.8% (87/213) | 1.4% (3/213) | 47.9% (102/213) | 11.8% (12/102) | 42.3% (90/213) | 52.1% (111/213) |
| phi3.5 | 85.9% (183/213) | 57.4% (105/183) | 36.6% (78/213) | 14.1% (30/213) | 66.2% (141/213) | 14.9% (21/141) | 56.3% (120/213) | 33.8% (72/213) |
| phi4 | 98.6% (210/213) | 94.3% (198/210) | 5.6% (12/213) | 1.4% (3/213) | 100.0% (213/213) | 22.5% (48/213) | 77.5% (165/213) | 0.0% (0/213) |
| qwen2.5:14b | 100.0% (213/213) | 91.5% (195/213) | 8.5% (18/213) | 0.0% (0/213) | 100.0% (213/213) | 15.5% (33/213) | 84.5% (180/213) | 0.0% (0/213) |
| qwen2.5:3b | 15.5% (33/213) | 0.0% (0/33) | 15.5% (33/213) | 84.5% (180/213) | 53.5% (114/213) | 21.1% (24/114) | 42.3% (90/213) | 46.5% (99/213) |
| qwen2.5:7b | 100.0% (213/213) | 78.9% (168/213) | 21.1% (45/213) | 0.0% (0/213) | 94.4% (201/213) | 17.9% (36/201) | 77.5% (165/213) | 5.6% (12/213) |

## TPC-H

### Primary correctness

| Model | Attempts | Governed correct / all | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 228 | 75.0% (171/228) | 0.0% (0/228) |
| llama3.1:8b | 228 | 92.1% (210/228) | 0.0% (0/228) |
| llama3.2:3b | 228 | 46.1% (105/228) | 0.0% (0/228) |
| mistral:7b | 228 | 47.4% (108/228) | 0.0% (0/228) |
| phi3.5 | 228 | 65.8% (150/228) | 0.0% (0/228) |
| phi4 | 228 | 93.4% (213/228) | 0.0% (0/228) |
| qwen2.5:14b | 228 | 98.7% (225/228) | 0.0% (0/228) |
| qwen2.5:3b | 228 | 5.3% (12/228) | 0.0% (0/228) |
| qwen2.5:7b | 228 | 93.4% (213/228) | 0.0% (0/228) |

### Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 76.3% (174/228) | 98.3% (171/174) | 1.3% (3/228) | 23.7% (54/228) | 92.1% (210/228) | 0.0% (0/210) | 92.1% (210/228) | 7.9% (18/228) |
| llama3.1:8b | 100.0% (228/228) | 92.1% (210/228) | 7.9% (18/228) | 0.0% (0/228) | 92.1% (210/228) | 0.0% (0/210) | 92.1% (210/228) | 7.9% (18/228) |
| llama3.2:3b | 78.9% (180/228) | 58.3% (105/180) | 32.9% (75/228) | 21.1% (48/228) | 46.1% (105/228) | 0.0% (0/105) | 46.1% (105/228) | 53.9% (123/228) |
| mistral:7b | 94.7% (216/228) | 50.0% (108/216) | 47.4% (108/228) | 5.3% (12/228) | 93.4% (213/228) | 0.0% (0/213) | 93.4% (213/228) | 6.6% (15/228) |
| phi3.5 | 84.2% (192/228) | 78.1% (150/192) | 18.4% (42/228) | 15.8% (36/228) | 50.0% (114/228) | 0.0% (0/114) | 50.0% (114/228) | 50.0% (114/228) |
| phi4 | 94.7% (216/228) | 98.6% (213/216) | 1.3% (3/228) | 5.3% (12/228) | 100.0% (228/228) | 0.0% (0/228) | 100.0% (228/228) | 0.0% (0/228) |
| qwen2.5:14b | 100.0% (228/228) | 98.7% (225/228) | 1.3% (3/228) | 0.0% (0/228) | 100.0% (228/228) | 0.0% (0/228) | 100.0% (228/228) | 0.0% (0/228) |
| qwen2.5:3b | 50.0% (114/228) | 10.5% (12/114) | 44.7% (102/228) | 50.0% (114/228) | 52.6% (120/228) | 0.0% (0/120) | 52.6% (120/228) | 47.4% (108/228) |
| qwen2.5:7b | 100.0% (228/228) | 93.4% (213/228) | 6.6% (15/228) | 0.0% (0/228) | 84.2% (192/228) | 0.0% (0/192) | 84.2% (192/228) | 15.8% (36/228) |

## Spider world_1

### Primary correctness

| Model | Attempts | Governed correct / all | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 93 | 100.0% (93/93) | 3.2% (3/93) |
| llama3.1:8b | 93 | 96.8% (90/93) | 9.7% (9/93) |
| llama3.2:3b | 93 | 74.2% (69/93) | 0.0% (0/93) |
| mistral:7b | 93 | 93.5% (87/93) | 3.2% (3/93) |
| phi3.5 | 93 | 90.3% (84/93) | 0.0% (0/93) |
| phi4 | 93 | 100.0% (93/93) | 6.5% (6/93) |
| qwen2.5:14b | 93 | 100.0% (93/93) | 3.2% (3/93) |
| qwen2.5:3b | 93 | 93.5% (87/93) | 6.5% (6/93) |
| qwen2.5:7b | 93 | 96.8% (90/93) | 12.9% (12/93) |

### Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 100.0% (93/93) | 100.0% (93/93) | 0.0% (0/93) | 0.0% (0/93) | 100.0% (93/93) | 3.2% (3/93) | 96.8% (90/93) | 0.0% (0/93) |
| llama3.1:8b | 100.0% (93/93) | 96.8% (90/93) | 3.2% (3/93) | 0.0% (0/93) | 100.0% (93/93) | 9.7% (9/93) | 90.3% (84/93) | 0.0% (0/93) |
| llama3.2:3b | 93.5% (87/93) | 79.3% (69/87) | 19.4% (18/93) | 6.5% (6/93) | 90.3% (84/93) | 0.0% (0/84) | 90.3% (84/93) | 9.7% (9/93) |
| mistral:7b | 100.0% (93/93) | 93.5% (87/93) | 6.5% (6/93) | 0.0% (0/93) | 64.5% (60/93) | 5.0% (3/60) | 61.3% (57/93) | 35.5% (33/93) |
| phi3.5 | 96.8% (90/93) | 93.3% (84/90) | 6.5% (6/93) | 3.2% (3/93) | 61.3% (57/93) | 0.0% (0/57) | 61.3% (57/93) | 38.7% (36/93) |
| phi4 | 100.0% (93/93) | 100.0% (93/93) | 0.0% (0/93) | 0.0% (0/93) | 100.0% (93/93) | 6.5% (6/93) | 93.5% (87/93) | 0.0% (0/93) |
| qwen2.5:14b | 100.0% (93/93) | 100.0% (93/93) | 0.0% (0/93) | 0.0% (0/93) | 100.0% (93/93) | 3.2% (3/93) | 96.8% (90/93) | 0.0% (0/93) |
| qwen2.5:3b | 100.0% (93/93) | 93.5% (87/93) | 6.5% (6/93) | 0.0% (0/93) | 83.9% (78/93) | 7.7% (6/78) | 77.4% (72/93) | 16.1% (15/93) |
| qwen2.5:7b | 100.0% (93/93) | 96.8% (90/93) | 3.2% (3/93) | 0.0% (0/93) | 96.8% (90/93) | 13.3% (12/90) | 83.9% (78/93) | 3.2% (3/93) |

## BIRD california_schools

### Primary correctness

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

### Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 100.0% (69/69) | 100.0% (69/69) | 0.0% (0/69) | 0.0% (0/69) | 52.2% (36/69) | 0.0% (0/36) | 52.2% (36/69) | 47.8% (33/69) |
| llama3.1:8b | 100.0% (69/69) | 78.3% (54/69) | 21.7% (15/69) | 0.0% (0/69) | 47.8% (33/69) | 9.1% (3/33) | 43.5% (30/69) | 52.2% (36/69) |
| llama3.2:3b | 65.2% (45/69) | 60.0% (27/45) | 26.1% (18/69) | 34.8% (24/69) | 47.8% (33/69) | 0.0% (0/33) | 47.8% (33/69) | 52.2% (36/69) |
| mistral:7b | 100.0% (69/69) | 82.6% (57/69) | 17.4% (12/69) | 0.0% (0/69) | 60.9% (42/69) | 7.1% (3/42) | 56.5% (39/69) | 39.1% (27/69) |
| phi3.5 | 100.0% (69/69) | 60.9% (42/69) | 39.1% (27/69) | 0.0% (0/69) | 47.8% (33/69) | 0.0% (0/33) | 47.8% (33/69) | 52.2% (36/69) |
| phi4 | 91.3% (63/69) | 95.2% (60/63) | 4.3% (3/69) | 8.7% (6/69) | 60.9% (42/69) | 0.0% (0/42) | 60.9% (42/69) | 39.1% (27/69) |
| qwen2.5:14b | 100.0% (69/69) | 100.0% (69/69) | 0.0% (0/69) | 0.0% (0/69) | 87.0% (60/69) | 10.0% (6/60) | 78.3% (54/69) | 13.0% (9/69) |
| qwen2.5:3b | 100.0% (69/69) | 60.9% (42/69) | 39.1% (27/69) | 0.0% (0/69) | 30.4% (21/69) | 14.3% (3/21) | 26.1% (18/69) | 69.6% (48/69) |
| qwen2.5:7b | 100.0% (69/69) | 100.0% (69/69) | 0.0% (0/69) | 0.0% (0/69) | 56.5% (39/69) | 15.4% (6/39) | 47.8% (33/69) | 43.5% (30/69) |

## Fixture

### Primary correctness

| Model | Attempts | Governed correct / all | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 30 | 10.0% (3/30) | 0.0% (0/30) |
| llama3.1:8b | 30 | 100.0% (30/30) | 0.0% (0/30) |
| llama3.2:3b | 30 | 80.0% (24/30) | 0.0% (0/30) |
| mistral:7b | 30 | 80.0% (24/30) | 0.0% (0/30) |
| phi3.5 | 30 | 20.0% (6/30) | 0.0% (0/30) |
| phi4 | 30 | 100.0% (30/30) | 0.0% (0/30) |
| qwen2.5:14b | 30 | 100.0% (30/30) | 10.0% (3/30) |
| qwen2.5:3b | 30 | 30.0% (9/30) | 0.0% (0/30) |
| qwen2.5:7b | 30 | 30.0% (9/30) | 0.0% (0/30) |

### Diagnostic breakdown

| Model | Gov. coverage (answered / all) | Gov. correct when answered | Gov. wrong / all | Gov. No scored answer / all | Raw coverage (answered / all) | Raw SQL correct when answered | Raw SQL wrong / all | Raw SQL No scored answer / all |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma2:9b | 10.0% (3/30) | 100.0% (3/3) | 0.0% (0/30) | 90.0% (27/30) | 50.0% (15/30) | 0.0% (0/15) | 50.0% (15/30) | 50.0% (15/30) |
| llama3.1:8b | 100.0% (30/30) | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/30) | 50.0% (15/30) | 0.0% (0/15) | 50.0% (15/30) | 50.0% (15/30) |
| llama3.2:3b | 100.0% (30/30) | 80.0% (24/30) | 20.0% (6/30) | 0.0% (0/30) | 80.0% (24/30) | 0.0% (0/24) | 80.0% (24/30) | 20.0% (6/30) |
| mistral:7b | 100.0% (30/30) | 80.0% (24/30) | 20.0% (6/30) | 0.0% (0/30) | 40.0% (12/30) | 0.0% (0/12) | 40.0% (12/30) | 60.0% (18/30) |
| phi3.5 | 20.0% (6/30) | 100.0% (6/6) | 0.0% (0/30) | 80.0% (24/30) | 0.0% (0/30) | NA (0/0) | 0.0% (0/30) | 100.0% (30/30) |
| phi4 | 100.0% (30/30) | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/30) | 90.0% (27/30) | 0.0% (0/27) | 90.0% (27/30) | 10.0% (3/30) |
| qwen2.5:14b | 100.0% (30/30) | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/30) | 80.0% (24/30) | 12.5% (3/24) | 70.0% (21/30) | 20.0% (6/30) |
| qwen2.5:3b | 30.0% (9/30) | 100.0% (9/9) | 0.0% (0/30) | 70.0% (21/30) | 0.0% (0/30) | NA (0/0) | 0.0% (0/30) | 100.0% (30/30) |
| qwen2.5:7b | 30.0% (9/30) | 100.0% (9/9) | 0.0% (0/30) | 70.0% (21/30) | 10.0% (3/30) | 0.0% (0/3) | 10.0% (3/30) | 90.0% (27/30) |

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
- **Validation checks.** (1) Legacy captures whose full result exceeded the
  stored row preview are compared by a stored exact hash rather than a
  rounding-normalized one, so a large result differing from expected only in
  precision could in principle be miscounted. To test whether this affected any
  published label, I ran an audit that replayed the eligible stored raw-SQL
  attempts and recovered the governed results affected by legacy truncation
  (780 fallback records: 15 AdventureWorks, 270 TPC-H, 495 BIRD), then re-scored
  them under the declared normalized comparison. It found no correct-to-wrong or
  wrong-to-correct changes among the compared results; replay errors are counted
  and reported separately. This is my own audit
  result, not an independently reproduced one; the audit script
  (`reexec_audit.py`) and a compact summary ([capture-normalization-audit.md](capture-normalization-audit.md))
  are published in the repository so it can be inspected. The default comparison no longer
  silently accepts the legacy exact hash for such a record: an unresolved
  truncated result is marked unscorable on both arms rather than compared by
  hash. Full-result recovery is opt-in (`--recover-raw`, `--recover-governed`);
  the published numbers come from that recovery path, which the audit above
  showed reproduces the same labels the earlier scoring recorded.
  (2) Card provenance is bound to the scoring inputs: each review records the
  capture SHA-256, the scoring commit, the dataset identity, and a
  model-case-run inventory, and the renderer re-verifies the capture hash and
  the observed run inventory (rejecting a hash mismatch, an incomplete run set,
  or an invalid record) and shows the scoring commit and the render-time commit
  separately. It also resolves the recorded dataset tree at the scoring revision,
  reconciles an independently declared expected-case inventory (from each pack's
  `golden.yml`) against the scored sample, and checks each printed rate against
  its numerator and denominator, refusing to emit a card on any mismatch. Neither
  check has changed a published number.
