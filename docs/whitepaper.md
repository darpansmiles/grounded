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

The tables below are in-catalog results from three runs across all five packs and nine local models. Run variance was approximately zero. The primary column, **governed correct / all**, divides correct answers by all in-catalog attempts, so refusals and failed attempts receive no correctness credit and one denominator applies to every model and both arms. **Correct / answered** is shown beside it as the conditional quality metric, and the gap between the two is coverage — a model can decline or fail to answer rather than answer wrongly. The [benchmark report](benchmarks.md) has the full primary and diagnostic tables (coverage, wrong-answer, and no-scored-answer rates for both arms), plus the other two scored dimensions.

### AdventureWorks

| Model | Governed correct / all | Governed correct / answered | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| phi4 | 93.0% (198/213) | 94.3% (198/210) | 22.5% (48/213) |
| qwen2.5:14b | 91.5% (195/213) | 91.5% (195/213) | 15.5% (33/213) |
| gemma2:9b | 80.3% (171/213) | 90.5% (171/189) | 14.1% (30/213) |
| llama3.1:8b | 87.3% (186/213) | 87.3% (186/213) | 5.6% (12/213) |
| qwen2.5:7b | 78.9% (168/213) | 78.9% (168/213) | 16.9% (36/213) |
| phi3.5 | 49.3% (105/213) | 57.4% (105/183) | 9.9% (21/213) |
| llama3.2:3b | 54.9% (117/213) | 62.9% (117/186) | 2.8% (6/213) |
| mistral:7b | 57.7% (123/213) | 58.6% (123/210) | 5.6% (12/213) |
| qwen2.5:3b | 0.0% (0/213) | 0.0% (0/33) | 11.3% (24/213) |

AdventureWorks makes the important point plainly: the governed result is not perfect. Stronger models have single-digit wrong-answer rates, while weaker models can be much less useful. The structural boundary prevents free-form SQL, but it does not prevent a model from selecting the wrong declared metric, period, dimension, or scope.

The raw-SQL arm is scored fairly: the same two-decimal rounding applied to the governed arm is applied to raw results before comparison, so a value that is correct but differently rounded is not counted as wrong. Under that symmetric comparison, raw-SQL correctness on AdventureWorks is not near-zero — the four capable models reach 14.1% to 22.5% correct over all attempts, against a governed correct/all of 78.9% to 93.0% for the same models. The gap to the governed arm is therefore reported against a raw baseline given full rounding credit, not an inflated one. The boundary also does not rescue a weak model: on AdventureWorks qwen2.5:3b produced correct answers on 0/213 governed attempts versus 24/213 raw (11.3%), so the governed advantage is a claim about the capable models, not a universal one. A sampled inspection of raw failures found genuine errors — wrong metric definitions, incorrect aggregations and joins, and references to schema that does not exist — but a complete, adjudicated classification across all packs is still open (see the benchmark report's limits).

### TPC-H

| Model | Governed correct / all | Governed correct / answered | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| qwen2.5:14b | 98.7% (225/228) | 98.7% (225/228) | 0.0% (0/228) |
| phi4 | 93.4% (213/228) | 98.6% (213/216) | 0.0% (0/228) |
| gemma2:9b | 75.0% (171/228) | 98.3% (171/174) | 0.0% (0/228) |
| qwen2.5:7b | 93.4% (213/228) | 93.4% (213/228) | 0.0% (0/228) |
| llama3.1:8b | 92.1% (210/228) | 92.1% (210/228) | 0.0% (0/228) |
| phi3.5 | 65.8% (150/228) | 78.1% (150/192) | 0.0% (0/228) |
| llama3.2:3b | 46.1% (105/228) | 58.3% (105/180) | 0.0% (0/228) |
| mistral:7b | 47.4% (108/228) | 50.0% (108/216) | 0.0% (0/228) |
| qwen2.5:3b | 5.3% (12/228) | 10.5% (12/114) | 0.0% (0/228) |

TPC-H exposes why a raw-SQL comparison must be diagnosed, not merely counted. The raw arm scored 0% correct on TPC-H for every model. A sampled diagnostic begins to classify why, rather than assuming it, though the buckets it assigns are heuristic — detecting a `SUM`, `COUNT`, or `JOIN` in an incorrect query does not by itself prove which operation caused the error, so these are indicative, not adjudicated. Some failures are schema hallucination: the models frequently reference classic TPC-H fields such as `part_type`, `part_brand`, and `market_segment` that were dimensionalized away in the gold star schema. Others are executed-but-wrong answers — queries that ran and returned the wrong number. For example, `SUM(extended_price)` returned 110,927,736,019.61 where the independently computed revenue was 50,992,515,249.66, and a `COUNT(order_key)` over the fact table returned 2,999,671 rather than 364,780 orders; these magnitudes are far too large to be rounding. Those examples establish that genuine errors are present. To check that no large result had merely been misjudged on precision, I ran an audit that replayed the eligible stored raw-SQL attempts and recovered the governed results affected by legacy truncation, and re-scored them under the corrected comparison; it found no correct-to-wrong or wrong-to-correct changes among the compared results, with replay errors reported separately. That is my own audit result, published with its script, rather than an independently reproduced one, and a complete, adjudicated root-cause classification of every raw failure remains heuristic; both are documented as limits in the benchmark report.

### Spider world_1

| Model | Governed correct / all | Governed correct / answered | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 100.0% (93/93) | 100.0% (93/93) | 3.2% (3/93) |
| phi4 | 100.0% (93/93) | 100.0% (93/93) | 6.5% (6/93) |
| qwen2.5:14b | 100.0% (93/93) | 100.0% (93/93) | 3.2% (3/93) |
| qwen2.5:7b | 96.8% (90/93) | 96.8% (90/93) | 12.9% (12/93) |
| llama3.1:8b | 96.8% (90/93) | 96.8% (90/93) | 9.7% (9/93) |
| mistral:7b | 93.5% (87/93) | 93.5% (87/93) | 3.2% (3/93) |
| qwen2.5:3b | 93.5% (87/93) | 93.5% (87/93) | 6.5% (6/93) |
| phi3.5 | 90.3% (84/93) | 93.3% (84/90) | 0.0% (0/93) |
| llama3.2:3b | 74.2% (69/93) | 79.3% (69/87) | 0.0% (0/93) |

### BIRD california_schools

| Model | Governed correct / all | Governed correct / answered | Raw SQL correct / all |
| --- | ---: | ---: | ---: |
| gemma2:9b | 100.0% (69/69) | 100.0% (69/69) | 0.0% (0/69) |
| qwen2.5:14b | 100.0% (69/69) | 100.0% (69/69) | 8.7% (6/69) |
| qwen2.5:7b | 100.0% (69/69) | 100.0% (69/69) | 8.7% (6/69) |
| phi4 | 87.0% (60/69) | 95.2% (60/63) | 0.0% (0/69) |
| mistral:7b | 82.6% (57/69) | 82.6% (57/69) | 4.3% (3/69) |
| llama3.1:8b | 78.3% (54/69) | 78.3% (54/69) | 4.3% (3/69) |
| phi3.5 | 60.9% (42/69) | 60.9% (42/69) | 0.0% (0/69) |
| qwen2.5:3b | 60.9% (42/69) | 60.9% (42/69) | 4.3% (3/69) |
| llama3.2:3b | 39.1% (27/69) | 60.0% (27/45) | 0.0% (0/69) |

### Fixture

The fixture is a tiny deterministic pack with 30 in-catalog cases per model,
and applicable denominators for some dimensions fall to 3–9 cases, so its rates
are noisy and do not carry the thesis. Governed correct / all ranged from
10.0% to 100.0% (the low values are models that mostly refuse this tiny pack);
among answered cases, correctness ranged 80.0% to 100.0%. The raw-SQL arm was 0% correct for
every model that had applicable cases except qwen2.5:14b (3 / 24, 12.5%); two
models (phi3.5, qwen2.5:3b) had no applicable raw cases and are reported as N/A,
not 0%. The full per-model denominators are in the
[benchmark report](benchmarks.md).

## What the thesis establishes and what it does not

**Structural claim.** The model can invoke only declared metric calls, so it cannot author free-form SQL and cannot schema-break at the boundary. The platform, rather than the model, computes the number, applies policy, and attaches evidence.

**Measured claim.** Across the five reviewed packs, tested local models, and three-run evaluation, the governed arm's correct answers over all in-catalog attempts were substantially higher than the raw-SQL arm's for the capable models (for example 78.9–93.0% versus 14.1–22.5% on AdventureWorks), and its remaining errors split between valid-but-wrong answers and unanswered cases rather than fabricated SQL. The raw-SQL arm had much lower correctness and materially different failure modes. These are results for these packs, models, prompts, and evaluation conditions.

**Not claimed.** Grounded does not establish universal correctness, general production readiness, a universal cost advantage, real-world adoption, or that every valid declared call is the right answer. It also does not establish that natural-language interaction is better than a report, selector, or direct SQL for every workflow.

These limits are the boundary of the thesis, not an apology for it. The evidence supports a narrower proposition: moving free-form SQL out of the model's authority changes the failure surface, and the remaining answer-level errors can be observed, counted, and improved.

## The argument this thesis advances

The business value case is an argument, not a measured outcome. Revenue is often a north-star business metric, and the people making sales, marketing, customer, and executive decisions need a common, trusted definition of it. A centrally managed governed MCP can make that definition available in a conversational workflow while keeping policy, verification, and evidence with the data platform rather than in a user prompt.

Consider a campaign manager asking about the performance of recent campaigns within a customer demographic, then using the result to shape a targeted campaign and assemble a stakeholder report. Consider an analyst preparing multi-year year-on-year and month-on-month business analysis with demographic cuts. The thesis contends that, in either workflow, a local economy model connected to a governed boundary can provide a cited answer without requiring the person to hop among a catalog, SQL workbench, dashboards, data owners, and chat tools for each question.

The intended trade is explicit. The central team accepts the work of maintaining the governed catalog and interface. In return, users may be able to ask for unfamiliar approved combinations of metrics, dimensions, and filters in plain language, while an economical model operates on declared context rather than reconstructing meaning and SQL from scratch. The value bar is net workflow benefit: time and effort saved must exceed the effort of correcting intent, inspecting the answer and evidence, and maintaining the catalog.

That argument remains to be tested with independent user sessions and a comparison against existing reporting and analytical interfaces. It should not be presented as a measured user outcome until those tests show that the proposed workflow is actually easier, faster, and sufficiently trustworthy for the people who would use it.
