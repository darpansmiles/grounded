# Foundations & build-vs-buy decision

Grounded is deliberately **commodity open-source tools + the governing glue we built on top**. This doc is the authoritative record of what we buy, what we build, and why.

## Decision

- **Buy the whole data stack as commodity OSS.** Ingestion = **dlt** (the industry-standard data load tool); transform = **SQLMesh**; semantic layer = **Cube**; lineage = **Marquez** (the OpenLineage reference server + UI). We build none of these — they're standard infrastructure, and using standard tools is what makes the result credible and reproducible for anyone who runs it.
- **Build the governing layer (the glue).** The genuinely new work is the layer that makes those tools safe for an AI agent: the metric resolver (metric definition → governed SQL → result), the governed MCP harness (list/describe/query_metric, check_policy, verify, audit), the two contracts (A: producer metadata; B: consumer semantics + policy), the **OpenLineage normalizer** that unifies dlt and SQLMesh into one event stream feeding Marquez, the thin agent, and the evals.
- **No bespoke black boxes.** Every infrastructure layer is standard OSS; the only thing that's "ours" is the governing glue — which is exactly where the product judgment lives. (Same discipline as using dlt instead of a hand-built mover: buy the commodity, build the differentiator.)

## Build-vs-buy map

| Grounded layer | Source | Status |
|---|---|---|
| Ingestion (source → bronze) | dlt | Buy |
| Transform (bronze → silver → gold) | SQLMesh | Buy |
| Semantic layer (metrics, dimensions) | Cube | Buy |
| Lineage server + UI (OpenLineage) | Marquez | Buy |
| **OpenLineage normalizer** (dlt `load_info` + SQLMesh column lineage → one event stream) | new | **Build (glue)** |
| **Metric resolver** (metric def → governed SQL → result) | new | **Build** |
| **Governed metric tree** (AOV = Revenue/Orders inherits lineage + policy) | new | **Build** |
| **Governance** (PII mask / row filter at query time) | new | **Build** |
| **MCP harness** (list/describe/query_metric, check_policy, verify, audit) | new | **Build** |
| **Lineage citation** (verified against Marquez's graph) | new | **Build** |
| **Thin agent** + example questions | new | **Build** |
| **Evals** (traces, golden set, error analysis, AI product metrics) | new | **Build** |

Everything tedious and standard, we buy; the new work concentrates on the governed-metric + MCP + evals layer — the AI-PM signal and the demo.

## What this means for the narrative

Grounded is "commodity OSS, knit together by a governing layer I built." Ingestion, transform, semantics, and lineage are all standard tools (dlt · SQLMesh · Cube · Marquez). The interview line: *"I didn't build a pile of tools to pad a portfolio. I took the standard open-source data stack and built the layer that makes it safe for an AI agent to query — the governed harness, the two contracts, and the normalizer that unifies lineage into one OpenLineage stream. The point is that I can reason across ingestion, governance, semantics, and agents, and I know which layer to build (the governed glue) and which to buy (everything else)."*

## Risks

- **Marquez is a running service.** It's a Docker stack (API + UI + its own Postgres), brought up with `make marquez-up`. Standard OSS, community-supported, so drift risk is low; a version bump is well-scoped.
- **The normalizer is the load-bearing glue.** It must map dlt's `load_info` and SQLMesh's column lineage into valid OpenLineage faithfully and **without hardcoding** — derived from the tools' own metadata so it works on any dataset (see slice 033b). This is where correctness lives and where the engineering shows.
- **Metric execution is ours.** The commodity tools catalog, transform, and trace; they do NOT resolve a business metric into governed SQL and execute it under policy. That resolver + harness is the net-new build and the heart of the product.
