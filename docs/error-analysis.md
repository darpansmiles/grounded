# Error Analysis: How Each Arm Fails

The headline number is that governed hallucination is zero — every model, every dataset, every run. That number is easy to state and easy to distrust. This document is the part that earns it: not *that* the arms differ, but *how* each one fails, with the actual broken SQL the ungoverned models produced.

The claim underneath the analysis is narrow on purpose. Governance does not make a small model smart. It changes what happens when the model is wrong.

## The ungoverned arm fails in two ways, and neither is "a slightly wrong number"

Give a local model the schema and ask it to write SQL directly, and it does not usually return a plausible-but-incorrect answer. It returns something that never runs.

Across all five datasets, the single most common ungoverned failure is the executor rejecting the model's output with **"only one SELECT statement is allowed"** — 408 times on TPC-H, 198 on Spider, 87 each on AdventureWorks and BIRD. The model wraps its query in commentary, emits two statements, or narrates its reasoning around the SQL. It does not produce one clean, executable query.

The second failure is schema hallucination: the model references columns and tables that do not exist.

```
Referenced column "part_type" not found in FROM clause!      ×27  (tpch)
Referenced column "part_brand" not found in FROM clause!     ×24  (tpch)
Referenced column "market_segment" not found in FROM clause! ×15  (tpch)
Referenced table  "customers" not found!                          (tpch)
Referenced table  "T2" / "T4" / "fl" not found!                   (invented aliases)
```

A representative ungoverned query, verbatim from the TPC-H card:

```sql
SELECT SUM(li.revenue - li.cost) AS margin FROM gold.fct_lineitem li GROUP BY 1;
```

`gold.fct_lineitem` has no `revenue` and no `cost` column — they are `extended_price`, `discount`, and `supply_cost`. The model invented the two columns that would have made the query easy, then failed on both.

Both failure classes land in the taxonomy as **`schema_break`** — *malformed or non-executable output* — not **`hallucination`**, which the taxonomy reserves for a *confident, executable answer that happens to be wrong*. That distinction matters, and it produces the most misread number in the whole result.

## phi4's "zero hallucination" is the trap, not the exception

On TPC-H, Spider, and the fixture, ungoverned **phi4 shows 0% hallucination.** Read alone, that looks like the biggest model is safe without governance.

It is the opposite. phi4's `schema_break_rate` on those datasets is ~100%. It never emitted a valid answer, so it never emitted a *confidently wrong* one. Its zero is a measurement of total breakage, not of safety.

**This is why `hallucination_rate` must always be read next to `schema_break_rate`.** A model that produces nothing cannot hallucinate. Reporting the first without the second would be the exact kind of overclaim this project is built to avoid. The honest reading: ungoverned, the largest local model failed *completely* on a real star schema; the smaller ones failed *loudly*, fabricating up to 100% of the time.

## The governed arm has exactly one failure mode, and it is never a wrong number

The governed model never writes SQL. It routes a question to a governed metric; the platform computes it. So the governed arm cannot schema-break and cannot fabricate a value — those failure modes are structurally unavailable to it. When it answers, `answer_correctness_when_answered` is **100%**, on every model and every dataset.

Its only way to miss is routing. It refuses a question it should have answered (over-refusal), or picks the wrong governed call. That is a real limitation — but it is a limitation of *coverage*, not of *trust*. A governed model that routes 60% of questions is 60% useful and 0% dangerous. An ungoverned model that answers everything is confidently wrong most of the time.

## Safety is model-independent; coverage is not

The clearest lesson is in the split between the two governed numbers.

`hallucination_rate` is 0% for the 3B model and the 14B model alike. The floor of safety does not move with model size, because the platform, not the model, is enforcing it.

Routing accuracy does move. The standout is `qwen2.5:3b` on AdventureWorks: 19.8% routing, 68.9% over-refusal, 5.6% correct — a small model that copes with uncertainty by refusing almost everything. Its hallucination rate is still exactly 0%. It became useless without ever becoming unsafe.

That is the whole shape of the result in one model. **Governance buys safety for free and at any size. Usefulness still has to be earned** — and it scales with capability. The two are decoupled, which is precisely what you want: you can swap in a better model to raise coverage without ever putting the safety floor at risk.

## The result holds across schemas nobody designed for it

Two of the datasets are warehouse-shaped and built here (AdventureWorks, TPC-H). Two are third-party text-to-SQL benchmarks queried as-is (Spider `world_1`, BIRD `california_schools`). Harder and messier schemas shift the governed routing numbers around — BIRD's dirty columns and the tiny fixture are the weakest — but governed hallucination stays at zero across all of them. The failure surface changes with the data. The safety floor does not.

## What the failures are for

Every error class here maps to a durable change, which is the point of running the analysis instead of just reporting the rate:

- The ungoverned arm's schema hallucination is not a bug to fix in the model. It is the argument for governance existing at all — it is what the governed arm structurally cannot do.
- Over-refusal on the small models is a *routing* problem, addressable by the planner prompt, not a safety problem.
- The `schema_break` vs `hallucination` split is a reporting discipline: never quote a safety number without its companion.

## Honest caveats

- **AdventureWorks is 6 of 9 models** in the comparison arm; the three slowest timed out on a 16 GB laptop. TPC-H and Spider are complete at 9/9. The governed 0% holds on every completed cell; the missing cells are compute, not evidence.
- **The resource figures measure the harness process, not the model.** RSS of 25–128 MB reflects the Python runner, not Ollama's loaded weights. Latency is real; the memory numbers are not a claim about model cost.
- **The faithfulness judge is a local model grading local models.** It is an additional axis, reported with its agreement against human labels, not treated as an oracle.
- **The fixture is a 13-row toy.** It exists to make the pipeline deterministic without Docker; its routing numbers are not meant to carry the argument.

Being wrong is a property of the system, not the model. The ungoverned arm is the measurement of what the governed arm prevents — not by being smarter, but by never letting the model hold the pen.
