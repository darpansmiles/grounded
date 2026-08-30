# Source A — PostgreSQL AdventureWorks OLTP

This is the real, normalized OLTP source for the production-spine phase. It is
independent of the small DuckDB fixture used by the existing fast test loop.

## Bring it up

```bash
make source-up
make source-load
make source-verify
```

`source-up` starts the pinned PostgreSQL 16.9 service on host port `5433` by
default. Set `SOURCE_HOST_PORT` to use an alternate host port when `5433` is
already occupied.
Cube similarly uses host port `4000` by default; set `CUBE_HOST_PORT` for an
isolated local run when that port is occupied.
Every data-stack Make target uses the active `DATASET` as its Compose project:
`make source-up DATASET=adventureworks` creates names such as
`grounded-adventureworks-postgres-1`; `make cube-up DATASET=tpch` creates
`grounded-tpch-cube-1`. `make down DATASET=<name>` stops that one project's
containers while retaining its volumes. The unattended benchmark queue brings
up one pack, runs it, and always downs it before moving to the next pack, so
only one source/Cube pair consumes laptop memory at a time.
`source-load` downloads, verifies, and restores the AdventureWorks dump into
that service; it is safe to repeat because it recreates the dedicated
`adventureworks` database. `source-verify` prints the required sales-domain table
counts. Stop the service while retaining the local database volume with
`docker compose -f infra/docker-compose.yml down`; remove its data deliberately
with `docker compose -f infra/docker-compose.yml down -v`.

Local development credentials are intentionally non-secret:

| Setting | Value |
| --- | --- |
| Host | `localhost` |
| Port | `5433` by default (`SOURCE_HOST_PORT` overrides it) |
| Database | `adventureworks` |
| User | `grounded` |
| Password | `grounded_local_password` |

## Persisting the source DSN

The ingestion boundary reads the pack-declared
`GROUNDED_ADVENTUREWORKS_SOURCE_DSN` from the environment or from the ignored
`.dlt/secrets.toml`. Persist it once without printing it:

```bash
GROUNDED_ADVENTUREWORKS_SOURCE_DSN='postgresql://…' make set-secret
```

`.dlt/secrets.toml.example` shows the exact key with no value. `make spine`
checks for this setting before starting a PostgreSQL-pack spine and prints the
same remediation rather than a Python traceback.

## Pinned source

The database service is the official `postgres:16.9-bookworm` image pinned to
`sha256:253815cf7579ffa05e1673d92e78d37273e61be0e4414e9a1449337d7925be94`.

`scripts/load_adventureworks.sh` restores the PostgreSQL-native AdventureWorks
2016 dump from Microsoft's MIT-licensed Azure Samples repository:

- dump URL: `https://raw.githubusercontent.com/Azure-Samples/postgresql-samples-databases/963247e830b98e96d7114712ee794730b5b0ee5a/postgresql-adventureworks/AdventureWorksPG.gz`
- dump SHA-256: `d1c7f7d761daf2dece57e099f37363fe316864fbc4c5f0ea3c6ca1c702217fe5`
- source repository commit: `963247e830b98e96d7114712ee794730b5b0ee5a`
- license: MIT, `Copyright (c) Microsoft Corporation`

The source is a PostgreSQL custom-format dump, rather than a SQL Server backup
or a runtime conversion. It restores directly with the container's
`pg_restore`; Grounded applies no schema or data massaging. Its native lower-case
identifiers match the pipeline contract (for example,
`sales.salesorderheader`).

## Loaded sales-domain tables

`make source-verify` checks these OLTP relations. The pinned dump produces the
following row counts:

| Table | Row count |
| --- | ---: |
| `sales.salesorderheader` | 31,465 |
| `sales.salesorderdetail` | 121,317 |
| `sales.customer` | 19,820 |
| `sales.salesterritory` | 10 |
| `production.product` | 504 |
| `production.productsubcategory` | 37 |
| `production.productcategory` | 4 |
| `person.person` | 19,972 |
| `person.emailaddress` | 19,972 |

The conversion is the normalized OLTP model, not AdventureWorksDW. It is source
A only: ingestion to bronze, SQLMesh, Cube, and any harness/resolver changes are
separate later slices.

## Ingestion to DuckDB bronze

Slice 029 ingests source A to the local DuckDB bronze layer with dlt 1.30.0.
It uses dlt's `sql_database` source against the nine sales-domain relations and
performs a full `replace` batch load.

```bash
make ingest
make bronze-verify
```

`make ingest` runs the `adventureworks_to_bronze` batch pipeline. It mirrors the
nine sales-domain relations into `data/adventureworks.duckdb` under the `bronze`
schema, using a full `replace` load. `make bronze-verify` compares every bronze
table's count against the live source A table and fails on any mismatch.

DLT warns that it cannot infer and therefore does not materialize source columns
that contain no values in this dump: `sales.salesorderheader.comment` and
`production.product.discontinueddate`. All populated columns and every row land
unchanged; Grounded applies no workaround or source-data mutation.

The DuckDB lakehouse and dlt state are local runtime data beneath `data/` and are
gitignored. The DuckDB PoC fixture is separately stored at `data/fixture.duckdb`.

### Metadata-derived OpenLineage handoff

The ingestion script writes `data/openlineage/ingest.jsonl`. It emits one
OpenLineage `START` and one `COMPLETE` event for the batch run to that JSONL sink.
The event identities and facets are derived from dlt's own completed-load
metadata: `load_info` supplies the load id and completed tables,
`pipeline.default_schema` supplies normalized column names and types, and
`pipeline.last_trace.last_normalize_info.row_counts` supplies per-table row
counts. The configured extraction resources map each loaded table to its
physical PostgreSQL source identity, so the handoff reflects the actual batch.

## Marquez lineage server

Slice 031 emits the real dlt and SQLMesh OpenLineage events to local Marquez.

```bash
make marquez-up
make lineage
curl http://localhost:5050/api/v1/namespaces
```

The Marquez API is at `http://localhost:5050`, its admin endpoint is at
`http://localhost:5051`, and the UI is at `http://localhost:3000`. The API and
admin container ports remain `5000` and `5001`; their host mappings avoid the
macOS AirPlay Receiver, which reserves host port `5000`. After `make lineage`,
open the UI to inspect the physical PostgreSQL-table → bronze → silver → gold
dataset graph. The `curl` command lists the namespaces created by the emitted
events.

The stack uses the pinned Marquez 0.50.0 API and web images, plus a dedicated
pinned Postgres 14 metadata database volume. Stop it while retaining lineage
metadata with `docker compose -f infra/docker-compose.yml down`; remove that
metadata deliberately with `docker compose -f infra/docker-compose.yml down -v`.

Before posting, the real-lineage normalizer enriches every RunEvent with the
OpenLineage 2.0.0 `schemaURL`. It records the dlt events as produced by
`infra/ingest.py` and derives SQLMesh events by iterating the loaded
`Context.models` and SQLMesh's `column_dependencies` API. Both producers use
the stable project URI `https://github.com/grounded-flagship/grounded`.

### Verification record

On 2026-08-16, `make marquez-up` reported Marquez, Marquez Web, and the
dedicated Postgres service healthy on the ports above. `make lineage` posted 12
events (2 dlt and 10 SQLMesh) with HTTP 2xx. The dlt events reported all nine
physical AdventureWorks source tables in the `postgres` namespace, and the
`gold.fct_sales` lineage response reached those physical sources through bronze
and silver.
