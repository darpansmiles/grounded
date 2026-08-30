# BIRD `california_schools` pack

This is one representative database from BIRD, not a BIRD leaderboard or a
full-suite execution-accuracy claim. It exercises a governed metric layer over
a third-party school-data schema, including real column names that require
careful semantic mapping.

## Provenance

The data is attributed to the [BIRD benchmark](https://bird-bench.github.io)
(HKU/Alibaba) and licensed CC BY-SA 4.0. It is extracted from the official
`bird-bench/mini_dev` release channel's
[`minidev.zip`](https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip)
archive. The extracted `california_schools.sqlite` file has SHA-256
`c0903eec662e63068fd1d14403d3d6c1d473287fc10c4356333ea58f878db983`.

The raw SQLite file is intentionally not committed. The exact archive path,
fetch command, and checksum verification are in
[source/README.md](source/README.md).

## Governed surface

The pack defines school count, total K–12 enrollment, and average SAT math
score, with county as the declared dimension. It intentionally does not expose
the full database as a text-to-SQL target. The `schools.Phone` field is masked
unless the role is `analyst_pii` or `admin`, so the pack demonstrates a PII
policy alongside the metric contract.
