# AdventureWorks Cube semantic layer

Run `make cube-up` after the local AdventureWorks lakehouse has been built by
the preceding source, movement, and transform steps. Cube listens at
`http://localhost:4000/cubejs-api/v1`; `http://localhost:4000/readyz` reports
when it is ready.

The `Sales` cube reads the read-only mounted `data/adventureworks.duckdb` file. Its
four real-data measures apply the gold `is_completed = TRUE` contract and its
three dimensions are backed by the product, territory, and date dimensions.
The deterministic PoC fixture never uses this service; it remains the default
resolver backend.
