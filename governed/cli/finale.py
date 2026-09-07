"""The interactive governed-versus-raw-SQL payoff for the guided tour."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

import yaml

from agent.agent import answer
from agent.ungoverned import answer_ungoverned, pack_schema_prompt
from governed.cli.narration import ROUTING_ANNOTATIONS
from models.provider import OllamaProvider, ProviderUnavailable
from packlib import Pack, load_pack

Input = Callable[[str], str]
Output = Callable[[str], None]
Answer = Callable[..., dict[str, Any]]
UngovernedAnswer = Callable[..., dict[str, Any]]


@contextmanager
def _active_pack(pack: Pack):
    previous = os.environ.get("GROUNDED_PACK")
    os.environ["GROUNDED_PACK"] = pack.name
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("GROUNDED_PACK", None)
        else:
            os.environ["GROUNDED_PACK"] = previous


def suggested_questions(pack: Pack) -> tuple[list[str], list[str]]:
    """Read examples directly from the committed golden set, never from narration."""
    with pack.golden.open(encoding="utf-8") as golden_file:
        cases = yaml.safe_load(golden_file)
    answers = [case["question"] for case in cases if case.get("expect", {}).get("type") == "metric"][:2]
    refusals = [case["question"] for case in cases if case.get("expect", {}).get("type") == "refuse"][:2]
    return answers, refusals


def _format(value: Any) -> str:
    return f"{value:.2f}" if isinstance(value, (float, Decimal)) else str(value)


def _show_governed(result: dict[str, Any], *, output: Output) -> str:
    if "message" in result:
        output(f"Governed result: REFUSED · {result['message']}")
        return "refuse"
    output("Governed result: one declared call, with a receipt")
    for row in result.get("answer_rows", []):
        output("  " + " | ".join(f"{key}: {_format(value)}" for key, value in row.items()))
    if result.get("metric_definition"):
        output(f"  Definition: {result['metric_definition']}")
    output(f"  Policy: {result.get('policy_applied') or 'none'}")
    output(f"  Verification: {result.get('verify_status')}")
    for check in result.get("verification", []):
        output(
            f"    {check.get('type')}:{check.get('field')} — "
            f"{check.get('status')} · {check.get('detail')}"
        )
    if result.get("lineage_citation"):
        output(f"  Lineage: {result['lineage_citation']}")
    if result.get("verify_status") is not None:
        return "query_metric"
    if result.get("metric_definition"):
        return "describe_metric"
    answer_rows = result.get("answer_rows", [])
    if answer_rows and all("metric" in row for row in answer_rows):
        return "list_metrics"
    return "other"


def _show_routing_annotation(outcome: str, *, output: Output) -> None:
    """Explain a declared non-metric call without changing the model's route."""
    annotation = ROUTING_ANNOTATIONS.get(outcome)
    if annotation:
        output(annotation)


def _show_ungoverned(result: dict[str, Any], *, output: Output) -> None:
    output("Ungoverned raw-SQL control:")
    if result["schema_break"]:
        output(f"  Schema break: {result['rejection_reason']}")
        output(f"  Raw attempt: {result['raw_sql']}")
        return
    output(f"  SQL: {result['sql']}")
    for row in result["rows"]:
        output("  " + " | ".join(f"{key}: {_format(value)}" for key, value in row.items()))


def run_interactive_finale(
    dataset: str,
    model: str,
    *,
    input_func: Input = input,
    output: Output = print,
    pack_loader: Callable[[str], Pack] = load_pack,
    governed_answer: Answer = answer,
    ungoverned_answer: UngovernedAnswer = answer_ungoverned,
    provider_factory: Callable[[str], OllamaProvider] = OllamaProvider,
) -> int:
    """Compare one governed tool route with the deliberately raw-SQL control arm."""
    pack = pack_loader(dataset)
    answers, refusals = suggested_questions(pack)
    output("\nThese examples come from this pack's committed evaluation set.")
    output("Should answer:")
    for question in answers:
        output(f"  - {question}")
    output("Should refuse:")
    for question in refusals:
        output(f"  - {question}")
    output("Ask your own question, or enter q to continue to the proof.")

    minimal_lineage = pack.transform_dir is None
    if minimal_lineage:
        if pack.source.type == "duckdb_seed":
            output(
                "Fixture runs Docker-free, so there is no Marquez lineage service; "
                "it shows its declared local provenance instead."
            )
        else:
            output(
                f"{pack.name} declares minimal local lineage, so there is no Marquez "
                "lineage service for this tour."
            )

    provider = provider_factory(model)
    lineage_logger = logging.getLogger("harness.lineage_source")
    previous_lineage_log_level = lineage_logger.level
    if minimal_lineage:
        lineage_logger.setLevel(logging.ERROR)
    with _active_pack(pack):
        try:
            while True:
                try:
                    question = input_func("Question: ").strip()
                except (EOFError, KeyboardInterrupt):
                    return 0
                if question.casefold() in {"q", "quit", "done", ""}:
                    return 0
                try:
                    governed = governed_answer(
                        question,
                        planner="llm",
                        provider=provider,
                        backend=pack.semantics.backend if pack.semantics else "fixture",
                        cube_url=os.environ.get("GROUNDED_CUBE_URL"),
                        db_path=str(pack.destination.path),
                    )
                    outcome = _show_governed(governed, output=output)
                    _show_routing_annotation(outcome, output=output)
                    control_prompt = (
                        pack_schema_prompt(str(pack.destination.path), pack.name, pack.transform_dir is not None)
                        if pack.semantics and pack.semantics.backend == "cube"
                        else None
                    )
                    ungoverned = ungoverned_answer(
                        question,
                        provider,
                        str(pack.destination.path),
                        dataset=pack.name if pack.semantics and pack.semantics.backend == "cube" else "fixture",
                        system_prompt=control_prompt,
                    )
                    _show_ungoverned(ungoverned, output=output)
                except (ProviderUnavailable, RuntimeError, ValueError) as exc:
                    output(f"The comparison could not run: {exc}")
                    return 2
        finally:
            lineage_logger.setLevel(previous_lineage_log_level)
