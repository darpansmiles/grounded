# TPC-H pack

This pack generates the TPC-H benchmark schema at scale factor **0.5** with
DuckDB's built-in `tpch` extension, copies the eight generated relations into
its own local PostgreSQL `tpch` database and schema, then uses dlt →
SQLMesh → Cube → Marquez.

## Provenance

TPC-H is the Transaction Processing Performance Council's decision-support
benchmark. This pack generates its local input rather than downloading a raw
database: DuckDB's bundled `tpch` extension creates the eight TPC-H relations
at SF=0.5 (`region`, `nation`, `supplier`, `customer`, `part`, `partsupp`,
`orders`, and `lineitem`). The generated data is then loaded into the local
PostgreSQL source. The pack uses `GROUNDED_TPCH_SOURCE_DSN`, independent of
the AdventureWorks source. See [source/README.md](source/README.md) for the
precise local-input contract.

There is no fetched third-party source file, pinned URL, or source-file
SHA-256 for this pack. The reproducibility pin is the declared generator,
schema, and scale factor. The TPC-H benchmark has its own usage terms; this
repository does not redistribute a TPC-H data file.

The pack owns `data/tpch.duckdb`; its `tpch` DuckDB catalog alias in `make
lakehouse` matches its `tpch.*` Marquez dataset namespace.

## Governed surface

The semantic layer deliberately exposes four business measures over fulfilled
order lines: discounted revenue, distinct orders, average order value
(revenue divided by orders), and margin after supplier cost. They can be
grouped by nation, region, market segment, part brand/type, and order month.

The pack demonstrates two independent controls: customer phone data is masked
unless the role is `analyst_pii` or `admin`, and `eu_analyst` is restricted to
the `EUROPE` region. These controls make the familiar benchmark schema useful
for testing governed metrics rather than unrestricted SQL generation.

## Sanity totals

Computed through the governed Cube query after the SF=0.5 load:

- Fulfilled-order revenue: **50,992,515,249.66**
- Distinct fulfilled orders: **364,780**

These values are a fixity check for future `make spine DATASET=tpch` runs;
they are not copied from a separate TPC-H implementation.
