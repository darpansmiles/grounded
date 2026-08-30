# Grounded spine

Grounded is a local, reproducible data-and-AI reference build. It proves one
bounded claim: an agent can answer a business question through a governed
surface, with policy enforcement, result verification, audit evidence, and a
lineage citation back to the source data.

## Implemented stack

```
PostgreSQL (AdventureWorks, TPC-H) ┐
SQLite (Spider, BIRD)              ├─ dlt ─► DuckDB: bronze
                                   │              │
                                   │              └─ SQLMesh ─► silver / gold
                                   │                              │
                                   └──────────────────────────► Cube semantics
                                                                  │
OpenLineage events ──────────────────────────────────────────► Marquez UI/API
                                                                  │
                                              governed MCP harness ─► agent
```

DuckDB is the embedded analytical engine for each dataset pack. It is not a
lakehouse: there is no object store or open-table-format layer. SQLMesh builds
the bronze-to-silver-to-gold models for packs that declare a transform; SQLite
packs can be queried directly when their manifest says no transform is needed.

## Dataset packs

A pack carries its source, destination, transformations where applicable,
semantic definitions, policies, golden set, and capability declaration. The
current packs are:

| Pack | Source | Data shape |
| --- | --- | --- |
| `adventureworks` | PostgreSQL | Sales warehouse transformed to a star schema |
| `tpch` | PostgreSQL | TPC-H warehouse transformed to a star schema |
| `spider_world1` | SQLite | External relational schema, no transform |
| `bird_ca_schools` | SQLite | External relational schema, no transform |
| `fixture` | Seeded DuckDB | Small deterministic walkthrough |

For AdventureWorks, the primary revenue path is
`bronze.salesorderdetail → silver.stg_sales_order_line → gold.fct_sales`.
The source order header contributes the completed-order status through
`bronze.salesorderheader → silver.stg_sales_order`.

## Happy path

1. A source pack is loaded and dlt writes its bronze relations to DuckDB.
2. SQLMesh builds and audits silver and gold relations when the pack declares a
   transform.
3. Cube exposes the pack's governed metrics and dimensions.
4. dlt and SQLMesh runtime metadata are normalized into OpenLineage events,
   which Marquez serves through its API and UI.
5. The MCP harness accepts a validated governed tool call, applies declared
   policy, executes the metric backend, verifies the result, appends an audit
   record, and returns a Contract-B citation.

The agent never receives a raw SQL tool or a raw database connection.

## Operating the spine

Install the project, persist the local AdventureWorks source DSN, and run all
pack spines:

```bash
python -m pip install -e .
GROUNDED_ADVENTUREWORKS_SOURCE_DSN='postgresql://…' make set-secret
make spine-all
```

`make demo` is the fast deterministic alternative: it rebuilds the fixture,
does not require Docker, and demonstrates the governed metric, policy, audit,
verification, and declared citation. See [QUICKSTART.md](../QUICKSTART.md) for
the full sequence, including the optional local-model benchmark.

## Definition of done

- A pack runs source → bronze → transform where declared → semantics → lineage.
- A governed query returns a definition, policies, verification status, audit
  evidence, and a citation.
- Sensitive reads and row filters are enforced by the harness rather than by
  the planner.
- The golden set and evaluation harness distinguish coverage failures from
  incorrect answers.
- The real lineage graph is inspectable in Marquez with `make lineage-view`.

## Deliberate boundaries

This is a reference build, not a production platform. It does not provide an
identity provider, enterprise authorization, sandboxing, streaming ingestion,
or a catalog. The governed boundary is documented in
[ai-strategy.md](ai-strategy.md).
