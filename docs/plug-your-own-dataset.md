# Plug your own dataset into Grounded

Create a pack, then validate it before running the governed pipeline:

```sh
make new-pack NAME=mydata
make validate-pack DATASET=mydata
make spine DATASET=mydata
make benchmark DATASET=mydata
make lakehouse
```

The scaffold starts with a small runnable DuckDB seed. Replace `source/seed.py`
and its table list, or configure PostgreSQL with `connection.dsn_env` (for example
`MYDATA_SOURCE_DSN`) or SQLite with a pack-relative `source.path`. The validator
checks the manifest and reports missing connection environment variables and missing
declared assets before a run.

Metrics in `semantics/` are the governed Contract-B surface; add the appropriate
mask, deny, or row-filter policy there. Keep an in-scope metric question and an
out-of-scope refusal in the golden set. Add SQLMesh only when the source needs a
transform, and select Cube when you add Cube models.

Reference implementations: AdventureWorks is the warehouse-style PostgreSQL pack;
TPC-H is the larger warehouse pack; Spider `world_1` and BIRD
`california_schools` are representative third-party SQLite schemas. The latter two
are demonstrations, not benchmark-leaderboard runs.
