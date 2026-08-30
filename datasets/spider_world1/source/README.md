# Spider `world_1` source

This pack is one representative Spider database, not a Spider leaderboard or a
full-suite execution-accuracy claim. It supports a narrow governed-metrics
surface over a third-party schema.

- Origin and attribution: [Yale LILY Spider 1.0](https://yale-lily.github.io/spider),
  CC BY-SA 4.0.
- Downloaded from the approved pinned mirror:
  [`Chinastark/spider_datasets@e78889179827ba6af803937c320e1f0632886c24`](https://huggingface.co/datasets/Chinastark/spider_datasets/resolve/e78889179827ba6af803937c320e1f0632886c24/database/world_1/world_1.sqlite)
- Mirror-internal path: `database/world_1/world_1.sqlite`
- Local target: `source/world_1.sqlite`
- SHA-256: `17b986695f16786d58d66f85e49dba87bdfe72953207ab9b1b49da9d2301ef65`

The raw SQLite file is intentionally ignored and not committed. Its verified
tables are `country`, `city`, and `countrylanguage`.

## Governed use

The public semantic surface is total population, country count, and total GNP,
grouped by continent or region. The `eu_analyst` role receives only rows whose
continent is `Europe`; questions outside these declared metrics and dimensions
are refused rather than answered with unrestricted SQL.

## Fetch locally

From the repository root, download the pinned file and verify it before running
this pack:

```bash
curl --fail --location \
  'https://huggingface.co/datasets/Chinastark/spider_datasets/resolve/e78889179827ba6af803937c320e1f0632886c24/database/world_1/world_1.sqlite' \
  --output datasets/spider_world1/source/world_1.sqlite
echo '17b986695f16786d58d66f85e49dba87bdfe72953207ab9b1b49da9d2301ef65  datasets/spider_world1/source/world_1.sqlite' | shasum -a 256 -c -
```
