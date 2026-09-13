"""Raw-arm truncated-capture audit — offline, deterministic, no Cube, no model.

Published audit tool (see docs/capture-normalization-audit.md for the receipt). Checks the RAW arm:
for every raw-SQL attempt, re-execute the stored SQL against the pinned local DuckDB,
recover the FULL result rows, and re-score with the repo's own normalized comparison
(`independent_rows` + `rows_match`). Reports whether any label flips vs the current
the current published scoring. The governed arm needs Cube/resolver and is handled by the scorer
hardening (the governed recovery path), not here.

Run from the repo root:
    .venv/bin/python reexec_audit.py
Optionally write per-record results:
    .venv/bin/python reexec_audit.py --write

Requires only the local data/<dataset>.duckdb files (read-only). No services.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import duckdb

from agent.ungoverned import extract_sql, is_single_select
from evals.offline_scoring import (
    TruthUnavailable,
    _aliases_for_metric,
    _iter_capture_records,
    independent_rows,
    rows_match,
)

PACKS = {
    "adventureworks": "aw-final-r3",
    "tpch": "tpch-final-r3",
    "spider_world1": "spider-final-r3",
    "bird_ca_schools": "bird-final-r3",
    "fixture": "fixture-final-r3",
}
CAP_DIR = Path(".grounded/captures")
DB_DIR = Path("data")


def _db_path(dataset: str) -> Path:
    return DB_DIR / f"{dataset}.duckdb"


def _execute_full_rows(dataset: str, sql: str) -> list[dict]:
    """Deterministically re-run the stored raw SQL and return ALL rows as dicts."""
    con = duckdb.connect(str(_db_path(dataset)), read_only=True)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        con.close()


def _preview_len(record: dict) -> int:
    raw = record.get("ungoverned") or {}
    rows = raw.get("rows") if raw else record.get("ungoverned_rows")
    return len(rows) if isinstance(rows, list) else 0


def _stored_row_count(record: dict):
    raw = record.get("ungoverned") or {}
    return raw.get("row_count", record.get("ungoverned_row_count"))


def _old_raw_label(record: dict) -> str:
    """Recompute the current published raw label from captured rows, so old vs new
    come from identical logic and only the row-recovery differs."""
    from evals.offline_scoring import captured_rows_match, _capture_hashes

    expected_metric = record.get("expect", {}).get("type") == "metric"
    if not expected_metric:
        return "n/a"
    dataset = record["_dataset"]
    try:
        expected_rows = independent_rows(dataset, record["expected_plan"], record["role"])
    except TruthUnavailable:
        return "n/a"
    metric = record.get("expected_plan", {}).get("args", {}).get("metric", "")
    aliases = _aliases_for_metric(metric) if isinstance(metric, str) else {}
    _g_c, _g_h, raw_count, raw_hash, legacy_hash = _capture_hashes(record)
    raw = record.get("ungoverned") or {}
    raw_rows = raw.get("rows") if raw else record.get("ungoverned_rows")
    raw_sql = extract_sql(raw.get("raw_sql") or record.get("ungoverned_sql") or "")
    if not raw_sql or raw_rows is None or expected_rows is None:
        return "n/a"
    return (
        "correct"
        if captured_rows_match(
            raw_rows, expected_rows, row_count=raw_count, content_hash=raw_hash,
            alias_map=aliases, metric=metric, legacy_hash=legacy_hash,
        )
        else "wrong"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write per-record results to .grounded/scores/*-raw-audit.json")
    args = ap.parse_args()

    grand = defaultdict(int)
    for dataset, stem in PACKS.items():
        cap = CAP_DIR / f"{stem}.jsonl"
        if not cap.is_file():
            print(f"[skip] {dataset}: no capture at {cap}")
            continue
        per_model = defaultdict(lambda: {"checked": 0, "truncated": 0, "flip_w2c": 0, "flip_c2w": 0, "reexec_error": 0})
        flips = []
        for ds, record in _iter_capture_records([cap]):
            if record.get("record_type") != "case":
                continue
            record["_dataset"] = ds
            if record.get("expect", {}).get("type") != "metric":
                continue
            raw = record.get("ungoverned") or {}
            raw_sql = extract_sql(raw.get("raw_sql") or record.get("ungoverned_sql") or "")
            if not raw_sql or not is_single_select(raw_sql):
                continue
            model = record.get("model", "?")
            m = per_model[model]
            m["checked"] += 1
            stored_count = _stored_row_count(record)
            truncated = isinstance(stored_count, int) and stored_count > _preview_len(record)
            if truncated:
                m["truncated"] += 1
            try:
                expected_rows = independent_rows(ds, record["expected_plan"], record["role"])
            except TruthUnavailable:
                continue
            metric = record.get("expected_plan", {}).get("args", {}).get("metric", "")
            aliases = _aliases_for_metric(metric) if isinstance(metric, str) else {}
            try:
                full_rows = _execute_full_rows(ds, raw_sql)
            except Exception as exc:  # noqa: BLE001 - report, do not guess
                m["reexec_error"] += 1
                flips.append((model, record.get("case_id"), record.get("run"), "REEXEC_ERROR", str(exc)[:120]))
                continue
            new_label = "correct" if rows_match(full_rows, expected_rows, alias_map=aliases, metric=metric) else "wrong"
            old_label = _old_raw_label(record)
            if old_label == "wrong" and new_label == "correct":
                m["flip_w2c"] += 1
                flips.append((model, record.get("case_id"), record.get("run"), "wrong->correct", f"{len(full_rows)} rows"))
            elif old_label == "correct" and new_label == "wrong":
                m["flip_c2w"] += 1
                flips.append((model, record.get("case_id"), record.get("run"), "correct->wrong", f"{len(full_rows)} rows"))

        print(f"\n===== {dataset} =====")
        tot = defaultdict(int)
        for model in sorted(per_model):
            s = per_model[model]
            for k, v in s.items():
                tot[k] += v
            print(f"  {model:16} checked={s['checked']:4} truncated={s['truncated']:4} "
                  f"flip w->c={s['flip_w2c']:3} c->w={s['flip_c2w']:3} err={s['reexec_error']:3}")
        print(f"  {'TOTAL':16} checked={tot['checked']:4} truncated={tot['truncated']:4} "
              f"flip w->c={tot['flip_w2c']:3} c->w={tot['flip_c2w']:3} err={tot['reexec_error']:3}")
        for k, v in tot.items():
            grand[k] += v
        if flips:
            print("  --- flips / errors ---")
            for f in flips[:50]:
                print("   ", f)
        if args.write:
            out = Path(".grounded/scores") / f"{stem}-raw-audit.json"
            out.write_text(json.dumps({"dataset": dataset, "per_model": per_model, "flips": flips}, indent=1, default=str))
            print(f"  wrote {out}")

    print(f"\n########## GRAND TOTAL (raw arm) ##########")
    print(f"  checked={grand['checked']} truncated={grand['truncated']} "
          f"flip wrong->correct={grand['flip_w2c']} correct->wrong={grand['flip_c2w']} reexec_error={grand['reexec_error']}")
    print("  (flip wrong->correct > 0 means published raw numbers move up; 0 means they stand.)")


if __name__ == "__main__":
    main()
