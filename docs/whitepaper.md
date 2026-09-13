# Grounded: a thesis for governed data answers

## Thesis

Grounded advances a narrow thesis: a governed boundary plus a declared metric catalog can let an economical local model answer enterprise data questions with trusted, traceable results. At the boundary, the model routes a declared call instead of authoring free-form SQL, so free-form-SQL fabrication is structurally removed. The errors that remain, including choosing a valid call for the wrong question, must be measured rather than hidden.

This is a thesis about a reference build and a measured system comparison. It is not a claim of universal correctness, production readiness, or demonstrated customer adoption.

## The problem

An ungoverned model handed a warehouse schema must infer metric meaning, joins, filters, SQL dialect, and an explanation in one response. It may produce a query that refers to a column or table that does not exist, or a query that executes but answers a different question. The problem is not only syntax. It is that a schema does not declare the approved meaning, policy, ownership, or evidence needed to decide whether a number should be trusted.

The surrounding interaction is changing. Business users are increasingly comfortable asking questions in natural language. Tools are becoming headless and connected to chat surfaces through MCP servers, plugins, and skills. A campaign manager may want to inspect performance across customer segments, reason about the next campaign, and produce a stakeholder report within one working context. An analyst may need a year-on-year and month-on-month view with demographic cuts, but otherwise has to discover datasets, validate definitions, query the warehouse, and move between a catalog, workbench, and reporting tool.

Grounded's argument is that these workflows make a governing layer more valuable, especially when cost pressure makes it unattractive to use the most capable model for every data question. The model can contribute interpretation and routing, while the system retains control of declared definitions, bounded execution, policy, and evidence.

## The approach: commodity stack, governing glue

Grounded is built around standard data infrastructure and a small governing layer. The reference build uses dlt for ingestion, DuckDB for analytical execution, SQLMesh for transformation, Cube for semantic exposure, and Marquez and OpenLineage for lineage. The point is not a new data platform. The point is the boundary that connects these assets to an agent.

Two contracts provide that boundary with machine-readable context:

- **Producer contract.** A data-producing layer declares its output, shape, freshness, quality, owner, and lineage as runtime records.
- **Consumer contract.** A semantic definition declares a metric's meaning, dimensions, policy, checks, owner, and lineage evidence.

The governing glue uses these contracts to admit only declared calls. A request is checked for a defined metric, permitted scope, and supported capability. It is then executed through the declared backend, verified against the declared checks, recorded for audit, and returned with a definition, policy record, verification outcome, and lineage citation.

This is deliberately narrower than a general SQL agent. The model may select a metric, dimensions, and filters from the declared vocabulary. It does not write the query that reaches the warehouse. A derived metric can inherit the policies and lineage of its parents, so the governing layer can apply the same scope to the whole computation rather than leaving the model to reconstruct it each time.

The catalog is a real operating cost. Definitions, dimensions, policies, checks, owners, and lineage references must be maintained as the data estate changes. Grounded does not contend that the catalog is free. It contends that this maintenance may be worthwhile when it replaces repeated interpretation and verification work at the point where a user asks for a consequential answer.

## The evidence: measured, independently scored

The evaluation asks: **For declared analytical tasks, what does a governed interface change about answer correctness, useful coverage, policy enforcement, and inspectability, and what does it cost?** It compares a catalog plus governed tools with a schema plus SQL. It does not isolate the effect of any one mechanism.

The evaluation captures the model's produced plan, executes each non-refusal governed plan using the case role, captures the raw-SQL control attempt, and scores both arms against independently computed direct SQL truth. It reports four dimensions: answer correctness, interface compliance, policy compliance, and evidence completeness. Each rate uses its applicable denominator, with answer correctness conditioned on answered, in-catalog cases. The evaluator self-test must detect five seeded failures before a report is valid: wrong metric, wrong period, duplicate result, missing evidence, and forbidden scope.

The tables below are in-catalog results from three runs across all five packs and nine local models. Run variance was approximately zero. “Correct” is shown as correct answers divided by answered cases. “Wrong” is shown as wrong answers divided by all in-catalog cases, including over-refusals in its denominator. The [benchmark report](benchmarks.md) provides the complete five-pack tables, including the other two scored dimensions and their denominators.

### AdventureWorks

| Model | Governed correct / answered | Governed wrong / in-catalog | Ungoverned correct / answered | Ungoverned wrong / in-catalog |
| --- | ---: | ---: | ---: | ---: |
| phi4 | 198 / 210 (94.3%) | 12 / 213 (5.6%) | 48 / 213 (22.5%) | 165 / 213 (77.5%) |
| qwen2.5:14b | 195 / 213 (91.5%) | 18 / 213 (8.5%) | 33 / 213 (15.5%) | 180 / 213 (84.5%) |
| gemma2:9b | 171 / 189 (90.5%) | 18 / 213 (8.5%) | 30 / 213 (14.1%) | 183 / 213 (85.9%) |
| llama3.1:8b | 186 / 213 (87.3%) | 27 / 213 (12.7%) | 12 / 210 (5.7%) | 198 / 213 (93.0%) |
| qwen2.5:7b | 168 / 213 (78.9%) | 45 / 213 (21.1%) | 36 / 201 (17.9%) | 165 / 213 (77.5%) |
| phi3.5 | 105 / 183 (57.4%) | 78 / 213 (36.6%) | 21 / 141 (14.9%) | 120 / 213 (56.3%) |
| llama3.2:3b | 117 / 186 (62.9%) | 69 / 213 (32.4%) | 6 / 129 (4.7%) | 123 / 213 (57.7%) |
| mistral:7b | 123 / 210 (58.6%) | 87 / 213 (40.8%) | 12 / 102 (11.8%) | 90 / 213 (42.3%) |
| qwen2.5:3b | 0 / 33 (0.0%) | 33 / 213 (15.5%) | 24 / 114 (21.1%) | 90 / 213 (42.3%) |

AdventureWorks makes the important point plainly: the governed result is not perfect. Stronger models have single-digit wrong-answer rates, while weaker models can be much less useful. The structural boundary prevents free-form SQL, but it does not prevent a model from selecting the wrong declared metric, period, dimension, or scope.

The raw-SQL arm is scored fairly: the same two-decimal rounding applied to the governed arm is applied to raw results before comparison, so a value that is correct but differently rounded is not counted as wrong. Under that symmetric comparison, raw-SQL correctness on AdventureWorks is not near-zero — it runs 4.7% to 22.5% across the nine models, and 14.1% to 22.5% across the four capable ones. The gap to the governed arm is therefore reported against a raw baseline given full rounding credit, not an inflated one. The boundary also does not rescue a weak model: qwen2.5:3b answered 0% correct under governance on AdventureWorks against 21.1% raw, so the governed advantage is a claim about the capable models, not a universal one. A sampled inspection of raw failures found genuine errors — wrong metric definitions, incorrect aggregations and joins, and references to schema that does not exist — but a complete, adjudicated classification across all packs is still open (see the benchmark report's limits).

### TPC-H

| Model | Governed correct / answered | Governed wrong / in-catalog | Ungoverned correct / answered | Ungoverned wrong / in-catalog |
| --- | ---: | ---: | ---: | ---: |
| qwen2.5:14b | 225 / 228 (98.7%) | 3 / 228 (1.3%) | 0 / 228 (0.0%) | 228 / 228 (100.0%) |
| phi4 | 213 / 216 (98.6%) | 3 / 228 (1.3%) | 0 / 228 (0.0%) | 228 / 228 (100.0%) |
| gemma2:9b | 171 / 174 (98.3%) | 3 / 228 (1.3%) | 0 / 210 (0.0%) | 210 / 228 (92.1%) |
| qwen2.5:7b | 213 / 228 (93.4%) | 15 / 228 (6.6%) | 0 / 192 (0.0%) | 192 / 228 (84.2%) |
| llama3.1:8b | 210 / 228 (92.1%) | 18 / 228 (7.9%) | 0 / 210 (0.0%) | 210 / 228 (92.1%) |
| phi3.5 | 150 / 192 (78.1%) | 42 / 228 (18.4%) | 0 / 114 (0.0%) | 114 / 228 (50.0%) |
| llama3.2:3b | 105 / 180 (58.3%) | 75 / 228 (32.9%) | 0 / 105 (0.0%) | 105 / 228 (46.1%) |
| mistral:7b | 108 / 216 (50.0%) | 108 / 228 (47.4%) | 0 / 213 (0.0%) | 213 / 228 (93.4%) |
| qwen2.5:3b | 12 / 114 (10.5%) | 102 / 228 (44.7%) | 0 / 120 (0.0%) | 120 / 228 (52.6%) |

TPC-H exposes why a raw-SQL comparison must be diagnosed, not merely counted. The raw arm scored 0% correct on TPC-H for every model. A sampled diagnostic begins to classify why, rather than assuming it, though the buckets it assigns are heuristic — detecting a `SUM`, `COUNT`, or `JOIN` in an incorrect query does not by itself prove which operation caused the error, so these are indicative, not adjudicated. Some failures are schema hallucination: the models frequently reference classic TPC-H fields such as `part_type`, `part_brand`, and `market_segment` that were dimensionalized away in the gold star schema. Others are executed-but-wrong answers — queries that ran and returned the wrong number. For example, `SUM(extended_price)` returned 110,927,736,019.61 where the independently computed revenue was 50,992,515,249.66, and a `COUNT(order_key)` over the fact table returned 2,999,671 rather than 364,780 orders; these magnitudes are far too large to be rounding. Those examples establish that genuine errors are present. To check that no large result had merely been misjudged on precision, I ran a full-result audit that re-executed every raw and governed attempt and re-scored it under the corrected comparison; no label changed. That is my own audit result, published with its script, rather than an independently reproduced one, and a complete, adjudicated root-cause classification of every raw failure remains heuristic; both are documented as limits in the benchmark report.

### Spider world_1

| Model | Governed correct / answered | Governed wrong / in-catalog | Ungoverned correct / answered |
| --- | ---: | ---: | ---: |
| gemma2:9b | 93 / 93 (100.0%) | 0 / 93 (0.0%) | 3 / 93 (3.2%) |
| phi4 | 93 / 93 (100.0%) | 0 / 93 (0.0%) | 6 / 93 (6.5%) |
| qwen2.5:14b | 93 / 93 (100.0%) | 0 / 93 (0.0%) | 3 / 93 (3.2%) |
| qwen2.5:7b | 90 / 93 (96.8%) | 3 / 93 (3.2%) | 12 / 90 (13.3%) |
| llama3.1:8b | 90 / 93 (96.8%) | 3 / 93 (3.2%) | 9 / 93 (9.7%) |
| mistral:7b | 87 / 93 (93.5%) | 6 / 93 (6.5%) | 3 / 60 (5.0%) |
| qwen2.5:3b | 87 / 93 (93.5%) | 6 / 93 (6.5%) | 6 / 78 (7.7%) |
| phi3.5 | 84 / 90 (93.3%) | 6 / 93 (6.5%) | 0 / 57 (0.0%) |
| llama3.2:3b | 69 / 87 (79.3%) | 18 / 93 (19.4%) | 0 / 84 (0.0%) |

### BIRD california_schools

| Model | Governed correct / answered | Governed wrong / in-catalog | Ungoverned correct / answered |
| --- | ---: | ---: | ---: |
| gemma2:9b | 69 / 69 (100.0%) | 0 / 69 (0.0%) | 0 / 36 (0.0%) |
| qwen2.5:14b | 69 / 69 (100.0%) | 0 / 69 (0.0%) | 6 / 60 (10.0%) |
| qwen2.5:7b | 69 / 69 (100.0%) | 0 / 69 (0.0%) | 6 / 39 (15.4%) |
| phi4 | 60 / 63 (95.2%) | 3 / 69 (4.3%) | 0 / 42 (0.0%) |
| mistral:7b | 57 / 69 (82.6%) | 12 / 69 (17.4%) | 3 / 42 (7.1%) |
| llama3.1:8b | 54 / 69 (78.3%) | 15 / 69 (21.7%) | 3 / 33 (9.1%) |
| phi3.5 | 42 / 69 (60.9%) | 27 / 69 (39.1%) | 0 / 33 (0.0%) |
| qwen2.5:3b | 42 / 69 (60.9%) | 27 / 69 (39.1%) | 3 / 21 (14.3%) |
| llama3.2:3b | 27 / 45 (60.0%) | 18 / 69 (26.1%) | 0 / 33 (0.0%) |

### Fixture

The fixture is a tiny deterministic pack with 30 in-catalog cases per model,
and applicable denominators for some dimensions fall to 3–9 cases, so its rates
are noisy and do not carry the thesis. Governed correctness among models that
returned an answer ranged from 80.0% (24 / 30) to 100.0%; governed wrong-answer
rates ranged from 0.0% to 20.0% (0–6 / 30). The raw-SQL arm was 0% correct for
every model that had applicable cases except qwen2.5:14b (3 / 24, 12.5%); two
models (phi3.5, qwen2.5:3b) had no applicable raw cases and are reported as N/A,
not 0%. The full per-model denominators are in the
[benchmark report](benchmarks.md).

## What the thesis establishes and what it does not

**Structural claim.** The model can invoke only declared metric calls, so it cannot author free-form SQL and cannot schema-break at the boundary. The platform, rather than the model, computes the number, applies policy, and attaches evidence.

**Measured claim.** Across the five reviewed packs, tested local models, and three-run evaluation, the governed arm produced non-zero but often low wrong-answer rates for stronger models. The raw-SQL arm had much lower correctness and materially different failure modes. These are results for these packs, models, prompts, and evaluation conditions.

**Not claimed.** Grounded does not establish universal correctness, general production readiness, a universal cost advantage, real-world adoption, or that every valid declared call is the right answer. It also does not establish that natural-language interaction is better than a report, selector, or direct SQL for every workflow.

These limits are the boundary of the thesis, not an apology for it. The evidence supports a narrower proposition: moving free-form SQL out of the model's authority changes the failure surface, and the remaining answer-level errors can be observed, counted, and improved.

## The argument this thesis advances

The business value case is an argument, not a measured outcome. Revenue is often a north-star business metric, and the people making sales, marketing, customer, and executive decisions need a common, trusted definition of it. A centrally managed governed MCP can make that definition available in a conversational workflow while keeping policy, verification, and evidence with the data platform rather than in a user prompt.

Consider a campaign manager asking about the performance of recent campaigns within a customer demographic, then using the result to shape a targeted campaign and assemble a stakeholder report. Consider an analyst preparing multi-year year-on-year and month-on-month business analysis with demographic cuts. The thesis contends that, in either workflow, a local economy model connected to a governed boundary can provide a cited answer without requiring the person to hop among a catalog, SQL workbench, dashboards, data owners, and chat tools for each question.

The intended trade is explicit. The central team accepts the work of maintaining the governed catalog and interface. In return, users may be able to ask for unfamiliar approved combinations of metrics, dimensions, and filters in plain language, while an economical model operates on declared context rather than reconstructing meaning and SQL from scratch. The value bar is net workflow benefit: time and effort saved must exceed the effort of correcting intent, inspecting the answer and evidence, and maintaining the catalog.

That argument remains to be tested with independent user sessions and a comparison against existing reporting and analytical interfaces. It should not be presented as a measured user outcome until those tests show that the proposed workflow is actually easier, faster, and sufficiently trustworthy for the people who would use it.
