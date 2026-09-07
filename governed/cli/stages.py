"""Capability-aware, inspectable stages for the guided quickstart."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from governed.cli.narration import (
    FIXTURE_NARRATION,
    FULL_TOUR_NARRATION,
    QUICK_RUN_NARRATION,
)
from governed.cli.style import Presenter
from harness.citation import render_citation
from packlib import Pack, load_pack
from policy.engine import check_policy, row_predicates_for_role

Input = Callable[[str], str]
Output = Callable[[str], None]
CommandRunner = Callable[..., Any]
PackLoader = Callable[[str], Pack]


def _run_make(
    target: str,
    dataset: str,
    *,
    runner: CommandRunner,
    output: Output,
    presenter: Presenter,
) -> bool:
    """Run an existing Make target for exactly the selected pack."""
    command = ["make", target, f"DATASET={dataset}"]
    try:
        result = runner(command, check=False, capture_output=True, text=True)
    except OSError:
        return False
    if runner is subprocess.run:
        log_path = Path(".grounded/logs") / f"{dataset}-{datetime.now(UTC):%Y%m%d}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write("$ " + " ".join(command) + "\n")
            log_file.write(getattr(result, "stdout", "") or "")
            log_file.write(getattr(result, "stderr", "") or "")
            log_file.write("\n")
        if result.returncode == 0:
            presenter.command(f"Machinery complete. Full log: {log_path}")
        else:
            output(getattr(result, "stdout", "") or "")
            output(getattr(result, "stderr", "") or "")
    return result.returncode == 0


def _definitions(pack: Pack) -> list[dict[str, Any]]:
    if pack.semantics is None:
        return []
    definitions: list[dict[str, Any]] = []
    for path in pack.semantics.metrics:
        with path.open(encoding="utf-8") as definition_file:
            definitions.append(yaml.safe_load(definition_file))
    return definitions


def _relations(pack: Pack, schemas: tuple[str, ...]) -> list[tuple[str, str, int]]:
    """Read the resulting catalog without changing the pack database."""
    if not pack.destination.path.is_file():
        raise RuntimeError(f"Expected artifact is missing: {pack.destination.path}")
    import duckdb

    names = ", ".join("'" + schema.replace("'", "''") + "'" for schema in schemas)
    with duckdb.connect(str(pack.destination.path), read_only=True) as connection:
        relations = connection.execute(
            f"""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ({names})
              AND table_name NOT LIKE '_dlt_%'
            ORDER BY table_schema, table_name
            """
        ).fetchall()
        rows: list[tuple[str, str, int]] = []
        for schema, table in relations:
            quoted_schema = schema.replace('"', '""')
            quoted_table = table.replace('"', '""')
            count = connection.execute(
                f'SELECT COUNT(*) FROM "{quoted_schema}"."{quoted_table}"'
            ).fetchone()[0]
            rows.append((schema, table, count))
    return rows


def _show_relations(pack: Pack, schemas: tuple[str, ...], *, presenter: Presenter) -> int:
    rows = _relations(pack, schemas)
    if not rows:
        raise RuntimeError(f"No {', '.join(schemas)} tables were found in {pack.destination.path}")
    presenter.panel("Declared data artifact", [f"{schema}.{table} · {count:,} rows" for schema, table, count in rows])
    return len(rows)


def _continue(*, input_func: Input, output: Output, presenter: Presenter, done: str, next_step: str) -> bool:
    try:
        answer = input_func(presenter.prompt(done, next_step)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer in {"n", "no"}:
        output("Stopping after this artifact. The selected pack will be cleaned up.")
        return False
    return True


def _header(step: int, total: int, title: str, *, presenter: Presenter) -> None:
    presenter.header(f"\nPart 1 of 3 · Setup — Step {step}/{total} · {title}")


def _show_semantic_layer(pack: Pack, *, presenter: Presenter) -> list[dict[str, Any]]:
    definitions = _definitions(pack)
    by_metric = {definition["metric"]: definition for definition in definitions}
    lines: list[str] = []
    for definition in definitions:
        declared_dimensions = definition.get("dimensions", [])
        if not declared_dimensions and definition.get("inherits"):
            declared_dimensions = [
                dimension
                for parent in definition["inherits"]
                for dimension in by_metric[parent].get("dimensions", [])
            ]
        dimensions = ", ".join(dict.fromkeys(dimension["name"] for dimension in declared_dimensions)) or "none"
        lines.append(f"{definition['label']} ({definition['metric']}) · dimensions: {dimensions}")
    presenter.panel("Declared metric contract", lines)
    return definitions


def _show_metric_tree(definitions: list[dict[str, Any]], *, presenter: Presenter) -> bool:
    derived_metrics = [
        definition for definition in definitions if definition.get("definition", {}).get("derived") == "ratio"
    ]
    if not derived_metrics:
        presenter.panel("Metric tree", ["This pack declares no derived metric, so this stage is skipped honestly."])
        return False

    parents = {definition["metric"]: definition for definition in definitions}
    lines: list[str] = []
    for derived in derived_metrics:
        numerator = derived["definition"]["numerator"]
        denominator = derived["definition"]["denominator"]
        inherited_policies = list(
            dict.fromkeys(
                policy["id"]
                for parent in (parents.get(numerator, {}), parents.get(denominator, {}))
                for policy in parent.get("policies", [])
            )
        )
        lines.extend([f"{derived['label']} = {numerator} / {denominator}", f"  Parents: {numerator}, {denominator}"])
        if inherited_policies:
            lines.append(f"  Inherited policy: {', '.join(inherited_policies)} is carried from the declared parents.")
    presenter.panel("Declared metric tree", lines)
    return True


def _show_policy(definitions: list[dict[str, Any]], *, presenter: Presenter) -> None:
    definition = next((item for item in definitions if item.get("policies")), None)
    if definition is None:
        presenter.panel("Declared policy decisions", ["This pack declares no policy rules."])
        return
    rows: list[list[str]] = []
    for policy in definition["policies"]:
        target = policy["applies_to"]
        if policy["rule"] == "mask":
            viewer = check_policy(target, "viewer", definition)
            elevated_role = policy.get("unless_role", ["admin"])[0]
            elevated = check_policy(target, elevated_role, definition)
            rows.extend(
                [[target, "viewer", viewer["decision"], "PII: viewers see a masked value"], [target, elevated_role, elevated["decision"], "role is entitled to raw PII"]]
            )
        elif policy["rule"] == "row_filter":
            filtered = row_predicates_for_role(definition, "eu_analyst")
            predicate = next(
                (item["predicate"] for item in filtered if item["id"] == policy["id"]),
                policy.get("predicate", "declared predicate"),
            )
            rows.extend([[target, "eu_analyst", f"row filter {predicate}", "analyst is scoped to declared rows"], [target, "viewer", "no role-specific filter", "no restriction declared for this role"]])
        else:
            decision = check_policy(target, "viewer", definition)
            rows.append([target, "viewer", decision["decision"], decision["reason"]])
    presenter.table("Declared policy decisions", ["Object / field", "Role", "Effect", "Why"], rows)


def _show_lineage_citation(definitions: list[dict[str, Any]], *, presenter: Presenter) -> None:
    definition = next((item for item in definitions if item.get("lineage")), None)
    if definition is None:
        raise RuntimeError("No declared lineage is available for this pack")
    presenter.panel("Declared lineage citation", [render_citation(definition)])


def _show_declared_local_lineage(definitions: list[dict[str, Any]], *, presenter: Presenter) -> None:
    """Show quick-pack provenance without claiming a full Marquez path ran."""
    definition = next((item for item in definitions if item.get("lineage")), None)
    if definition is None:
        raise RuntimeError("No declared lineage is available for this pack")
    lineage = definition["lineage"]
    presenter.panel("Declared local lineage", [f"{definition['metric']} ← Tables:[{', '.join(lineage['tables'])}] ← Source:[{', '.join(lineage['sources'])}]"])


def run_stage_walk(
    dataset: str,
    *,
    input_func: Input = input,
    output: Output = print,
    runner: CommandRunner = subprocess.run,
    pack_loader: PackLoader = load_pack,
) -> int:
    """Run the declared stages, showing a real artifact after every action."""
    pack = pack_loader(dataset)
    is_full_tour = pack.transform_dir is not None
    total = 6 if is_full_tour else 4
    definitions = _definitions(pack)
    presenter = Presenter(output)

    if is_full_tour:
        _header(1, total, "Data movement", presenter=presenter)
        output(FULL_TOUR_NARRATION["movement"])
        for target in ("source-load", "ingest", "bronze-verify"):
            output(f"Running `make {target} DATASET={dataset}`...")
            if not _run_make(target, dataset, runner=runner, output=output, presenter=presenter):
                output(f"Data movement stopped: `make {target} DATASET={dataset}` failed.")
                return 2
        table_count = _show_relations(pack, (pack.destination.dataset,), presenter=presenter)
        output("  OpenLineage load event emitted to data/openlineage/ingest.jsonl")
        if not _continue(input_func=input_func, output=output, presenter=presenter, done=f"moved {table_count} source tables into bronze and emitted an OpenLineage load event.", next_step="transform bronze into a silver-to-gold analytical shape."):
            return 1

        _header(2, total, "Transformation", presenter=presenter)
        output(FULL_TOUR_NARRATION["transform"])
        output(f"Running `make transform DATASET={dataset}`...")
        if not _run_make("transform", dataset, runner=runner, output=output, presenter=presenter):
            output(f"Transformation stopped: `make transform DATASET={dataset}` failed.")
            return 2
        table_count = _show_relations(pack, ("silver", "gold"), presenter=presenter)
        output("  SQLMesh column lineage is available for the declared gold model.")
        if not _continue(input_func=input_func, output=output, presenter=presenter, done=f"built and audited {table_count} silver and gold relations.", next_step="read the declared semantic contract instead of inferring meaning from tables."):
            return 1
    else:
        narration = FIXTURE_NARRATION if pack.source.type == "duckdb_seed" else QUICK_RUN_NARRATION
        output(f"Skipped: data movement and transformation. {narration}")

    _header(3 if is_full_tour else 1, total, "Semantic layer", presenter=presenter)
    output(FULL_TOUR_NARRATION["semantic"])
    _show_semantic_layer(pack, presenter=presenter)
    if not _continue(input_func=input_func, output=output, presenter=presenter, done=f"read {len(definitions)} declared metrics and their dimensions.", next_step="trace how a derived metric inherits from its declared parents."):
        return 1

    _header(4 if is_full_tour else 2, total, "Metric tree", presenter=presenter)
    output(FULL_TOUR_NARRATION["metric_tree"])
    _show_metric_tree(definitions, presenter=presenter)
    if not _continue(input_func=input_func, output=output, presenter=presenter, done="showed the declared metric composition and inherited governance.", next_step="inspect the evidence path that supports a declared answer."):
        return 1

    _header(5 if is_full_tour else 3, total, "End-to-end lineage", presenter=presenter)
    if is_full_tour:
        output(FULL_TOUR_NARRATION["lineage"])
        try:
            start_marquez = input_func("Start Marquez to view the lineage graph? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            start_marquez = ""
        if start_marquez not in {"n", "no"}:
            output("Running `make marquez-up`...")
            if not _run_make("marquez-up", dataset, runner=runner, output=output, presenter=presenter):
                output("Lineage UI did not start: `make marquez-up` failed.")
                return 2
            output(f"Running `make lineage DATASET={dataset}`...")
            if not _run_make("lineage", dataset, runner=runner, output=output, presenter=presenter):
                output(f"Lineage emission stopped: `make lineage DATASET={dataset}` failed.")
                return 2
            output("Opening http://localhost:3000 in your browser...")
            if not _run_make("lineage-view", dataset, runner=runner, output=output, presenter=presenter):
                output("Could not open the lineage UI. Visit http://localhost:3000 manually.")
            output("In Marquez, select the adventureworks namespace, open the job graph, and follow source → bronze → silver → gold → Cube.")
            output("Open gold.fct_sales to inspect its column-level lineage. It is the same path summarized in the citation below.")
            output("On Apple Silicon, the amd64/arm64 image warning is expected and can be ignored.")
        else:
            output("Marquez was not started. The declared citation remains inspectable below.")
        _show_lineage_citation(definitions, presenter=presenter)
    else:
        output("End-to-end Marquez lineage is skipped: this quick-run pack declares minimal local lineage.")
        _show_declared_local_lineage(definitions, presenter=presenter)
    if not _continue(input_func=input_func, output=output, presenter=presenter, done="showed the declared path from source to metric.", next_step="apply declared policy before any answer can execute."):
        return 1

    _header(6 if is_full_tour else 4, total, "Policies", presenter=presenter)
    output(FULL_TOUR_NARRATION["policy"])
    _show_policy(definitions, presenter=presenter)
    if not _continue(input_func=input_func, output=output, presenter=presenter, done="applied declared policy decisions before execution.", next_step="move from setup to the governed-versus-raw-SQL test."):
        return 1
    return 0
