# Tool selection tradeoffs

Grounded buys commodity infrastructure and builds the governed agent boundary.
The table records the implemented choices rather than an aspirational design.

| Decision | Chosen | Why / boundary |
| --- | --- | --- |
| Source | PostgreSQL for AdventureWorks and TPC-H; SQLite for Spider and BIRD | Matches the source each pack actually provides and keeps external benchmark schemas intact. |
| Ingestion | dlt | Python-first ingestion with runtime metadata that can be normalized into lineage. |
| Analytical engine | DuckDB | Embedded, reproducible analytical execution for bronze, silver, gold, and direct-query packs. It is not a lakehouse. |
| Transformation | SQLMesh | Declarative bronze-to-silver-to-gold models and runtime column-lineage access for transformed packs. |
| Semantics | Cube | A real semantic API over gold models rather than exposing a hand-written SQL interface to an agent. |
| Lineage | Marquez + OpenLineage | Standard server and UI for producer-to-dataset lineage and impact queries. |
| Agent interface | Governed MCP harness | A small validated tool surface where policy, verification, audit, and citations are applied consistently. |
| Orchestration | Make targets | Small, inspectable local workflow; each pack can be run or benchmarked independently. |
| Evaluation | Golden sets plus governed and ungoverned arms | Measures routing, refusals, schema failures, and incorrect answers instead of treating a fluent answer as success. |

## What Grounded builds

Grounded does not reimplement movement, transformation, semantics, or lineage
storage. Its owned layer is the contracts, runtime lineage normalizer,
pack-aware metric resolver, policy translation, verification, audit trail, MCP
surface, thin planner, and evaluation harness.

## What it deliberately leaves outside the boundary

Identity, authentication, network isolation, sandboxing, enterprise
authorization, streaming, and a full metadata catalog are not claimed as
capabilities of this reference build. The platform's governing boundary is
described in [ai-strategy.md](ai-strategy.md).
