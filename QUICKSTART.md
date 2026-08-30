# Quickstart

Grounded has a deterministic fixture demo and a local multi-pack spine. The fixture is the fastest way to see the governed boundary; the full spine needs Docker Desktop and local source credentials.

## 1. Install

```bash
git clone <your-grounded-repository-url>
cd grounded
python3.13 -m venv .venv
.venv/bin/python -m pip install -e .
```

`pip install -e .` is required: Make targets and scripts import the installed project packages rather than relying on the shell's current directory.

## 2. Run the no-Docker walkthrough

```bash
make demo
```

This recreates the small fixture and prints a governed revenue answer, verification status, policy decisions, audit evidence, and a declared citation. It does not require a model or a running lineage service.

## 3. Configure the local sources once

With Docker Desktop running, persist the independent AdventureWorks and TPC-H
source DSNs without placing them in Git:

```bash
GROUNDED_ADVENTUREWORKS_SOURCE_DSN='postgresql://USER:PASSWORD@localhost:5433/adventureworks' \
GROUNDED_TPCH_SOURCE_DSN='postgresql://USER:PASSWORD@localhost:5433/tpch' \
make set-secret
```

The values are saved in ignored `.dlt/secrets.toml`. You may instead prepare
that file from `.dlt/secrets.toml.example`. The command reports a missing value
without printing a secret. Each pack owns its source database; TPC-H never
depends on the AdventureWorks database.

If the default local ports are already in use, choose isolated host ports for
this run and make the source DSN use the same PostgreSQL port:

```bash
SOURCE_HOST_PORT=5434 CUBE_HOST_PORT=4001 \
GROUNDED_ADVENTUREWORKS_SOURCE_DSN='postgresql://USER:PASSWORD@localhost:5434/adventureworks' \
GROUNDED_TPCH_SOURCE_DSN='postgresql://USER:PASSWORD@localhost:5434/tpch' \
make set-secret
SOURCE_HOST_PORT=5434 CUBE_HOST_PORT=4001 make spine-all
```

## 4. Build the pack spines

```bash
make spine-all
```

The command runs each reproducible pack's declared stages and releases each
pack's local source and Cube service before starting the next. For transformed
packs the flow is source → dlt bronze → SQLMesh silver/gold → Cube →
OpenLineage/Marquez. SQLite packs skip stages their manifest does not declare.
A fresh clone reports Spider and BIRD as skipped until their third-party SQLite
sources are fetched; their [Spider instructions](datasets/spider_world1/source/README.md)
and [BIRD instructions](datasets/bird_ca_schools/source/README.md) give pinned
downloads and checksums. After fetching either source, run `make spine
DATASET=spider_world1` or `make spine DATASET=bird_ca_schools`. Inspect the
real lineage UI after a run with:

```bash
make lineage-view
```

Use `make lakehouse DATASET=adventureworks` to inspect the local pack database.

## 5. Verify the repository

```bash
make test
make release-scrub
```

## 6. Run a local benchmark (your machine)

The benchmark uses locally available Ollama models and can take a long time. It is intentionally the user's local job, not part of the deterministic demo.

```bash
make benchmark DATASET=tpch
```

For a full local queue, run `make benchmark-all`. Models run one at a time on a 16 GB machine; request concurrency within a loaded model can be tuned with `OLLAMA_NUM_PARALLEL`. Versioned result cards are written under `evals/results/`.
