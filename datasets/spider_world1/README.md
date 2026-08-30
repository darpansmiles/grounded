# Spider `world_1` pack

This is one representative database from Spider, not a Spider leaderboard or
a full-suite execution-accuracy claim. It shows whether the governed metric
surface can operate on a third-party schema that Grounded did not design.

## Provenance

The data is attributed to [Yale LILY Spider 1.0](https://yale-lily.github.io/spider)
and licensed CC BY-SA 4.0. The pack fetches the `world_1` SQLite database from
the pinned `Chinastark/spider_datasets` mirror revision
[`e78889179827ba6af803937c320e1f0632886c24`](https://huggingface.co/datasets/Chinastark/spider_datasets/resolve/e78889179827ba6af803937c320e1f0632886c24/database/world_1/world_1.sqlite).
Its SHA-256 is
`17b986695f16786d58d66f85e49dba87bdfe72953207ab9b1b49da9d2301ef65`.

The raw SQLite file is intentionally not committed. The complete fetch and
verification instructions are in [source/README.md](source/README.md).

## Governed surface

The pack exposes only three country-level metrics: total population, country
count, and total GNP, with `continent` and `region` dimensions. This narrow
semantic layer is intentional: questions outside it are refused rather than
translated into ad hoc SQL over the wider Spider schema. The `eu_analyst` role
is restricted to countries whose continent is `Europe`, demonstrating a
row-level governance control.
