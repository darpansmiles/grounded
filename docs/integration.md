# The glue: what we built on top of commodity open source

Grounded is deliberately **commodity open-source tools plus a governing layer we built**. The tools are bought; the layer that makes them safe for an AI agent is the product. This document is the honest account of that layer — the "glue" — because the glue is where the engineering judgment is, and it's the part a reader can't get from a list of dependencies.

## The stack we bought

Four standard tools do the undifferentiated heavy lifting, each swapped in without touching the layer above it:

- **dlt** ingests the source into **DuckDB** — our embedded analytical (OLAP) engine — as bronze. (DuckDB is the analytical store/compute, not a lakehouse; there's no open-table-format/object-store layer.)
- **SQLMesh** transforms bronze → silver → gold and computes column-level lineage.
- **Cube** is the semantic layer: it exposes governed metrics and dimensions over gold.
- **Marquez** is the lineage server and UI — the OpenLineage reference implementation.

None of these is bespoke. Using standard tools is what makes the result reproducible for someone else, and it's the correct build-vs-buy call: you don't hand-roll ingestion, transformation, a semantic layer, or a lineage store to prove a point about governance.

## The glue we built (and why each piece is non-trivial)

### 1. The OpenLineage normalizer — one lineage stream from heterogeneous tools

Marquez only speaks OpenLineage. dlt and SQLMesh do not emit it: dlt exposes a `load_info`/trace object, and SQLMesh exposes a column-lineage graph through its `Context` API. Neither is an OpenLineage event stream. The normalizer is the adapter that turns both into one valid OpenLineage stream feeding Marquez.

The judgment here is that it derives everything from the tools' own runtime state rather than a hand-maintained description that would drift the moment the data changed: loaded tables and the load id from dlt's `load_info`, column types from dlt's normalized schema, row counts from dlt's normalize trace, and column-level edges from SQLMesh's `column_dependencies`. Nothing about the schema is hardcoded — the same emitter produces correct lineage for a schema it has never seen, which is what makes lineage correct when a stranger runs their own data. The events are enriched to be genuinely spec-valid (a `producer` URI and schema URLs), so Marquez accepts them rather than rejecting them — we fixed our events to meet the standard instead of weakening the standard.

### 2. Two contracts — the seams that let layers evolve independently

**Contract A** is the producer promise: on every run, an OpenLineage-shaped event stating what dataset now exists, its shape, freshness, row count, and origin. **Contract B** is the consumer promise, published by the semantic layer: a governed metric, its definition, owner, the policies that apply, its lineage, and how to verify it. The metric tree is the join between them. Because the contracts are stable, we could run the entire system on a thirteen-row fixture and then swap in real Postgres + dlt + SQLMesh + Cube without changing the agent — and later swap the bespoke lineage engine for Marquez without changing the harness.

### 3. The metric resolver and the governed harness

The commodity tools catalog, transform, and trace; none of them resolves a business metric into governed SQL and executes it under policy. That resolver is net-new and is the heart of the product. It sits behind a **backend seam**: a deterministic hand-SQL fixture backend for the fast no-Docker loop, and a Cube backend for the real spine. Governance sits *above* the seam, unchanged, so both backends are governed identically.

The harness is the interface the agent actually calls — list, describe, and query metrics; check policy; verify; audit; cite lineage. The boundary is deliberate and is the senior part of the design: the platform governs *definitions, policy, verification, audit, and lineage*; it does not do identity, authentication, or sandboxing. Naming what the platform does **not** own is what keeps the argument credible.

### 4. Governance translation — declarative, because inference would lie

Row and column policies are enforced by translating a policy declaration into a trusted, server-side Cube filter. The instructive detail: the Cube member a policy must filter often can't be derived from the policy's target — in AdventureWorks the country filter projects through a different physical source than the one the policy names. Rather than infer it (which would rebuild the implicit coupling we were trying to remove), the policy **declares** the member it targets. Governance mappings that can't be derived are stated explicitly and visibly in the policy — which is exactly what an auditor wants: to read what filter applies and why, not to reverse-engineer it.

### 5. The dataset-pack abstraction — the whole engine, made generic

A **pack** is a self-contained dataset: its source, transform, semantics, governance, and golden set, plus a manifest declaring which capabilities it has. The pipeline reads the active pack from a single seam (`GROUNDED_PACK`), and every layer — ingestion, transform, lineage, the resolver, governance, the ungoverned control arm, and the planner — resolves against that pack. A pack can be a Postgres warehouse with a SQLMesh transform (AdventureWorks, TPC-H) or a single SQLite schema queried directly with no transform (Spider, BIRD); the pipeline branches on declared capability rather than assuming one shape.

Physically, each pack is its own DuckDB database (its own file), and a read-only `ATTACH` presents them together as one analytical store — so datasets are isolated (a bad run can't corrupt another pack) yet queryable side by side as `pack.layer.table`. That physical identity deliberately mirrors the lineage identity in Marquez (`pack.layer:table`): the data store and the lineage graph address things the same way.

Getting to "generic" meant paying down every place the engine had quietly assumed AdventureWorks — the transform's audit list, the resolver's dimension validation, the empty-bucket contract, the control arm's schema, and the planner's vocabulary each had to be made pack-driven. The proof that it worked is that a brand-new dataset can be scaffolded from a template and run end to end — source, lineage, governed metrics, policy, and the full benchmark — with **zero changes to shared code**.

### 6. Governed-result contracts that show judgment

A few small decisions carry disproportionate weight because they're where a naive system fabricates or crashes. An aggregate over a group with no facts returns **zero for an additive measure** (a sum of no revenue is zero) but **null for a ratio** (an average over no rows is undefined, not zero) — the platform never invents a number and never crashes on an empty bucket. Lineage is **real and per-table**, not collapsed into a single aggregate source node, because table-level lineage is what a citation is actually for. Same-named tables across packs get **pack-scoped namespaces** so two datasets never merge into one wrong node.

### 7. The evaluation harness — the non-delegable part

The evals are their own build: traces → a golden set → a failure taxonomy (correct, correct-refusal, hallucination, over-refusal, schema-break) → distributions rather than averages. The headline is `hallucination_rate`; routing coverage is reported separately so the two are never conflated. The runner bounds each model with a wall-clock timeout and records a slow model as `incomplete` rather than fabricating its numbers or hanging the run. This is the part that caught our own regressions — a brittle routing prompt showed up as over-refusal in the distributions and drove the fix.

## Why this is the interesting layer

The commodity tools are excellent and we lean on them fully. But the thing that makes an AI agent safe over a data platform is none of them individually — it's the governing layer that unifies lineage into one auditable stream, resolves governed metrics under policy, states its own boundary, and generalizes to any dataset without code changes. That layer is what we built, and knowing which layer to build versus buy is the whole point.
