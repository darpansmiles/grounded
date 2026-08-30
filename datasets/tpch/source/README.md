# TPC-H generated source

This source is generated locally, not downloaded. DuckDB's built-in `tpch`
extension generates the TPC-H schema at scale factor **0.5**, then the pack
loader initializes its own local PostgreSQL `tpch` database and copies the
eight generated relations into its `tpch` schema. It uses
`GROUNDED_TPCH_SOURCE_DSN`; it does not reuse the AdventureWorks source. The
benchmark is attributed to the Transaction Processing Performance Council
(TPC); Grounded does not vendor or redistribute a TPC-H data file.

Because no external artifact is fetched, there is no mirror revision, archive
URL, or source-file SHA-256 to record. Reproducibility is defined by the
generator (`DuckDB tpch`), the scale factor (`0.5`), and the declared table
set: `region`, `nation`, `supplier`, `customer`, `part`, `partsupp`, `orders`,
and `lineitem`.

The generated source supports a narrow governed analytic surface: fulfilled
revenue, orders, average order value, and margin. Customer phone data is
masked for ordinary roles, and the `eu_analyst` role is constrained to the
`EUROPE` region. The metric and policy declarations are in the pack's
`semantics/` directory.
