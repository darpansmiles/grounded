# Grounded

Grounded is a reference build for governed data agents: instead of asking a model to write unrestricted SQL, it validates one declared MCP tool call, executes a governed metric, applies policy, verifies the result, records an audit event, and returns a lineage citation. That makes a fabricated numeric answer structurally unavailable at the execution boundary; model quality still matters for routing and coverage.

## Architecture

```
PostgreSQL (AdventureWorks, TPC-H) or SQLite (Spider, BIRD)
  → dlt → DuckDB (bronze → silver → gold) → SQLMesh → Cube
  → governed MCP harness → local agent
                     └→ OpenLineage → Marquez lineage API and UI
```

DuckDB is the embedded analytical engine. The governed layer owns contracts, metric resolution, policy enforcement, verification, audit, citations, and the evaluation harness; it does not claim to own identity or sandboxing.

## Start here

The complete clone-to-demo path is in [QUICKSTART.md](QUICKSTART.md). The fast deterministic walkthrough is `make demo`; `make spine-all` runs the local pack spines after a source DSN has been configured.

## Headline results

Across five dataset packs and up to nine local models, every completed governed comparison recorded **0% hallucination**. The paired comparisons report bootstrap confidence intervals and exact McNemar tests; routing accuracy and over-refusal remain visible rather than being hidden by the safety result. AdventureWorks has six completed models in the comparison; the remaining packs have eight or nine. See [benchmarks.md](docs/benchmarks.md) for methodology, tables, caveats, and broken-SQL examples.

## Read the design

- [Integration](docs/integration.md): the runtime seams and pack lifecycle.
- [Foundations](docs/foundations.md): what is bought and what Grounded builds.
- [AI strategy](docs/ai-strategy.md): the governance-versus-identity boundary.
- [Benchmarks](docs/benchmarks.md): evaluation method and results.
- [MCP tools](docs/mcp-tools.md), [metrics](docs/metrics.md), and [error analysis](docs/error-analysis.md): operational contracts and failure evidence.
