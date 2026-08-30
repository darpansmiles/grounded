# Source setup

This runnable starter uses `duckdb_seed` and `seed.py`. Replace it with your own
seed/generator, or select PostgreSQL with a `connection.dsn_env` such as
`MYDATA_SOURCE_DSN`, then export that variable before `make spine`. For SQLite,
place the file at the manifest's pack-relative `source.path`; list bare table names.
