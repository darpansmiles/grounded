# Architecture

## Runtime dependencies actually used

Grounded's local development environment uses Homebrew Python 3.13.15.
The application stack uses dlt 1.30.0 for ingestion, SQLMesh 0.236.1 for
transforms, Cube 1.7.19 as the semantic service, Marquez 0.50.0 for lineage,
and MCP 2.1.1 for transport. The published editable install also declares the
dlt SQL-source extra, psycopg2-binary 2.9.12, pytest 9.1.1, HTTPX 0.28.1,
PyYAML 6.0.3, Pydantic 2.13.5, and psutil 7.2.2 so the documented local spine
and `make test` have their required runtime tools.

## MCP transport

The MCP SDK exposes `MCPServer` in `mcp.server.mcpserver`. Grounded's thin
stdio server registers its governed tools from the local `harness/` package,
which owns tool dispatch, policy, verification, audit, citation, and lineage
reads.

## Packaging and script execution boundary

Grounded is an editable-installable Python project. Setuptools discovers the
top-level runtime packages, including dataset-pack modules, so a documented
`pip install -e .` makes package imports available outside the checkout.
Make exports the repository root as `PYTHONPATH` to every recipe and its
parse-time pack probes. Each executable in `scripts/` independently prepends
that same root before importing project code, so direct script execution has
the same import contract rather than relying on the caller's working directory.

## Governed semantic definitions

`semantics.loader.load_expanded_definition` is the single semantic-definition
boundary for metric inheritance. Base definitions pass through; derived ratio
definitions inherit compatible dimensions and the ordered union of parent
lineage tables, sources, and policies. The resolver compiles only declared
base `sum` and `count_distinct` measures. `governed_query` composes a derived
ratio from governed parent queries, so inherited row filtering is enforced on
both parents before division.

## Production-spine boundaries

Local Docker PostgreSQL AdventureWorks OLTP is ingested to the `bronze` schema
of a separate local DuckDB file by dlt. SQLMesh transforms that data into
`silver` staging models and `gold` star-schema views. Cube serves the declared
semantic metrics over those gold relations. The governed harness remains above
both the fixture and Cube resolver backends, keeping policy, verification,
audit, and Contract-B citation behavior independent of the calculation backend.
The Cube backend validates a request's dimensions by resolving the active
metric's declared dimensions against that pack's Cube model; the fixture
backend alone retains its fixed local-column map. This keeps the public
Contract-B dimension vocabulary pack-driven while preserving the fixture's
deliberately small deterministic SQL surface.
For Cube time/group buckets with no matching facts, the governed result
contract is measure-type-aware: additive `sum`/`count` metrics normalize a
null aggregate to zero, while derived ratios retain null because zero divided
by zero is undefined. This is query-result normalization only and is separate
from PII masking.

## Benchmark execution boundary

Each local model receives a configurable wall-clock budget (30 minutes by
default) for governed benchmark evaluation. A timeout unloads that model and
persists it as `incomplete` with reason `timeout`; completed models keep their
normal scorecards. The comparison card therefore remains usable without
inventing scores for a model that did not finish.

Benchmark operations are deliberately sequential across models because the
local target machine cannot keep multiple model weights resident. For one
loaded model, `OLLAMA_NUM_PARALLEL` (or the benchmark `--concurrency` override)
bounds concurrent requests, with a conservative default of two. All packs can
be spined and benchmarked through an unattended, resumable queue; partial cards
merge only when their model sets are disjoint and retain their independent
timing records rather than asserting a synthetic elapsed duration. PostgreSQL
source credentials stay local in ignored `.dlt/secrets.toml`, named by each
pack manifest and populated by `make set-secret`. Before the queue benchmarks a
Cube-backed pack, it invokes that pack's `make cube-up` flow so Cube is pointed
at the active pack's semantic model rather than retaining a previous dataset's
configuration.
The local source and Cube host ports default to `5433` and `4000`; callers can
override them with `SOURCE_HOST_PORT` and `CUBE_HOST_PORT` for an isolated run.
For a data-backed pack, its source and Cube services run under the Compose
project `grounded-<dataset>` and are torn down in a `finally` block before the
queue advances. This frees container memory without removing the pack's local
volumes; the separately managed Marquez service remains outside that lifecycle.

## Dataset-pack boundary

`packlib` loads the active dataset pack from `GROUNDED_PACK` (defaulting to
`adventureworks`). A pack owns its source declaration, DuckDB destination,
optional SQLMesh and semantic assets, golden set, and only the *name* of its
credential environment variable. The AdventureWorks pack is located at
`datasets/adventureworks/`; its PostgreSQL DSN is supplied locally through the
declared environment variable or untracked dlt secrets. The `datasets/fixture/`
pack owns the deterministic 13-row DuckDB seed and uses the fixture resolver
without SQLMesh, Cube, Docker, or live Marquez. Make maps `DATASET=<name>` to
that one selection seam and branches on these declared capabilities, so
ingestion, SQLMesh, Cube, semantic loading, lineage jobs, and the benchmark
resolve only the active pack's assets.

Each pack owns an isolated DuckDB file through `destination.path`: the
AdventureWorks spine uses `data/adventureworks.duckdb`, and future full packs
use the same `data/<pack>.duckdb` form. `make lakehouse` opens a read-only
unified session and attaches available pack files under their
`lineage_namespace`, so physical identifiers such as
`adventureworks.gold.dim_customer` mirror Marquez identities such as
`adventureworks.gold:dim_customer` without cross-pack writes or relation
collisions. Cube, SQLMesh, dlt, and the raw-SQL control arm all use the active
pack's declared database/model rather than an AdventureWorks global.

Pack source capabilities are explicit. PostgreSQL packs use dlt and their
declared DSN; SQLite packs declare a safe pack-relative `source.path` plus bare
table names. The SQLite file is deliberately checked only at ingestion time,
because third-party raw data is user-fetched rather than vendored. The
all-pack spine and benchmark queue report a missing SQLite source as skipped
with its pack README path, then continue with reproducible packs. DuckDB's
official `sqlite` extension attaches that file and copies declared tables to
the pack's `bronze` schema, emitting equivalent source-to-bronze OpenLineage
events under `<pack>.sqlite`. A pack with no SQLMesh transform queries `bronze`
in its raw-SQL control arm and emits only that source-to-bronze lineage; packs
with transforms retain the existing `gold` control schema and SQLMesh lineage.

The planner is pack-driven at the same boundary. It builds its prompt and
validation vocabulary from each active pack's Contract-B metric definitions:
metric names, each metric's allowed dimensions, the declared monthly filter
vocabulary where present, policy targets, and lineage datasets. This keeps the
LLM-facing surface aligned with the resolver without using the fixture's
physical-column map; malformed or undeclared calls still become a refusal.

The prompt-ablation runner renders four generic variants (`minimal`, the
current `027-generalized`, `verbose`, and `adversarial-terse`) from that same
active-pack vocabulary. It re-runs only the governed routing benchmark for
each variant and reports seeded bootstrap confidence intervals for routing and
governed hallucination. Prompt choice can affect routing, while the validated
execution boundary prevents an invalid model proposal from becoming an answer;
the ablation report preserves the individual benchmark samples so an observed
counterexample is visible rather than averaged away.

## Marquez lineage boundary

dlt and SQLMesh expose lineage differently. `ontology.real_lineage` normalizes
both producer formats into OpenLineage RunEvents and delivers them to the local
Marquez API. Marquez is the sole durable lineage service and its UI at
`http://localhost:3000` is the whole-spine lineage view. The harness reads
Marquez's REST graph endpoint through `harness.lineage_source` for impact and
Contract-B graph verification. Deterministic fixture tests use recorded API
responses through the same seam, so CI requires no running lineage service.

## Optional faithfulness judge boundary

The eval model card can optionally add an LLM-judged `faithfulness_rate` for
both governed and ungoverned answers. The judge receives only a question, the
serialized answer, and the same governed ground truth used by the control arm;
it cannot influence query execution, policy, verification, routing, or the
correctness taxonomy.
