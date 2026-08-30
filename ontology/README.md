# Grounded lineage normalization

`real_lineage.py` turns dlt's producer JSONL and SQLMesh model metadata into
one OpenLineage event stream, then delivers it to the local Marquez service.
It normalizes the physical PostgreSQL source identifiers to the logical
`postgres.adventureworks` dataset and preserves the bronze, silver, and gold
dataset identities used by the governed harness.

Run `make marquez-up` followed by `make lineage` to emit the current real
spine. Browse `http://localhost:3000` or query Marquez's REST API at
`http://localhost:5050` to inspect the resulting dataset lineage.
