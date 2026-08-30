# BIRD `california_schools` source

This pack is one representative BIRD database, not a BIRD leaderboard or a
full-suite execution-accuracy claim. It supports a narrow governed-metrics
surface over a third-party schema.

- Origin and attribution: [BIRD benchmark](https://bird-bench.github.io),
  HKU/Alibaba, CC BY-SA 4.0.
- Official resolved archive:
  [`minidev.zip`](https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip)
  from the `bird-bench/mini_dev` release channel (HTTP ETag
  `7BEB6DAB11E65F0FDE563E644A1EA319`, last modified 2024-06-20).
- Archive-internal path:
  `minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite`
- Local target: `source/california_schools.sqlite`
- SHA-256: `c0903eec662e63068fd1d14403d3d6c1d473287fc10c4356333ea58f878db983`

The raw SQLite file is intentionally ignored and not committed. Its verified
tables are `schools`, `frpm`, and `satscores`.

## Governed use

The public semantic surface is school count, total K–12 enrollment, and
average SAT math score, grouped by county. `schools.Phone` is masked unless
the role is `analyst_pii` or `admin`. Questions outside that metric and policy
surface are not treated as unrestricted SQL requests.

## Fetch locally

From the repository root, download the pinned archive, extract only this
database, and verify it before running this pack:

```bash
download_dir=$(mktemp -d)
curl --fail --location 'https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip' --output "$download_dir/minidev.zip"
unzip -p "$download_dir/minidev.zip" 'minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite' > datasets/bird_ca_schools/source/california_schools.sqlite
echo 'c0903eec662e63068fd1d14403d3d6c1d473287fc10c4356333ea58f878db983  datasets/bird_ca_schools/source/california_schools.sqlite' | shasum -a 256 -c -
rm -rf "$download_dir"
```
