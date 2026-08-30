from __future__ import annotations

import yaml

from harness.citation import render_citation
from packlib import active_pack


def test_render_citation_matches_contract_b_lineage():
    revenue_path = next(
        path for path in active_pack().semantics.metrics if path.stem == "revenue"
    )
    with revenue_path.open(encoding="utf-8") as revenue_file:
        revenue_definition = yaml.safe_load(revenue_file)

    assert render_citation(revenue_definition) == (
        "revenue ← Cube:Sales.revenue ← SQLMesh:gold.fct_sales "
        "← Tables:[gold.fct_sales, silver.stg_sales_order_line, bronze.salesorderdetail] "
        "← Source:[postgres.adventureworks]"
    )
