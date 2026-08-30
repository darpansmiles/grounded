"""Build the governed-vs-ungoverned model card for the benchmark control arm."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import wraps
from pathlib import Path
from typing import Any

import duckdb

from agent.ungoverned import answer_ungoverned, pack_schema_prompt
from evals.benchmark import (
    load_golden_cases,
    run_benchmark,
)
from evals.ground_truth import control_cases, ground_truth_for_case
from evals.judge import (
    DEFAULT_JUDGE_MODEL,
    faithfulness_rate,
    judge_agreement,
    load_judge_labels,
)
from evals.roster import model_roster
from evals.stats import bootstrap_rate_ci, mcnemar_exact, run_variance
from governed.service import governed_query
from models.provider import LLMProvider, OllamaProvider, ProviderUnavailable
from packlib import Pack, load_pack
from resolver.backends.cube import CubeResponseError

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_EXEMPLARS_PER_BUCKET = 5
MAX_PERSISTED_RAW_OUTPUT_CHARS = 2_000
MAX_PERSISTED_ERROR_CHARS = 500


def _activate_pack(dataset: str) -> Pack:
    """Select one validated pack for this evaluation process."""
    pack = load_pack(dataset)
    if pack.semantics is None:
        raise ValueError(
            f"Dataset pack {dataset!r} does not declare a semantic backend"
        )
    os.environ["GROUNDED_PACK"] = pack.name
    return pack


def _with_active_pack(function: Callable[..., Any]) -> Callable[..., Any]:
    """Scope GROUNDED_PACK to one evaluation call without leaking it to callers."""

    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        dataset = kwargs.get("dataset", "fixture")
        previous = os.environ.get("GROUNDED_PACK")
        try:
            _activate_pack(dataset)
            return function(*args, **kwargs)
        finally:
            if previous is None:
                os.environ.pop("GROUNDED_PACK", None)
            else:
                os.environ["GROUNDED_PACK"] = previous

    return wrapped


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _normalized_rows(
    rows: list[dict[str, Any]] | None,
) -> set[tuple[tuple[str, Any], ...]] | None:
    if rows is None:
        return None
    return {
        tuple(sorted((key, _json_value(value)) for key, value in row.items()))
        for row in rows
    }


def ungoverned_correct(result: dict[str, Any], truth: dict[str, Any]) -> bool:
    """Compare raw result rows with governed metric truth; refusal cases have no answer."""
    return (
        truth["type"] == "metric"
        and not result["schema_break"]
        and _normalized_rows(result["rows"]) == _normalized_rows(truth["rows"])
    )


def _rate(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _answered_precision(samples: list[dict[str, Any]]) -> float:
    answered = [sample for sample in samples if sample["label"] == "correct_answer"]
    # The guarded arm can only execute a correctly routed governed metric call.
    # With no answered case, its conditional precision remains the structural 1.0.
    return 1.0 if not answered else _rate([True for _ in answered])


def _governed_label(sample: dict[str, Any], expected_type: str) -> str:
    """Classify a guarded plan: invalid routing becomes safe coverage loss, never fabrication."""
    if expected_type == "metric" and sample["routing_correct"]:
        return "correct_answer"
    if expected_type == "refuse" and sample["produced_plan"]["tool"] == "refuse":
        return "correct_refusal"
    return "over_refusal"


def _governed_card(
    governed_card: dict[str, Any],
    samples: list[dict[str, Any]],
    metric_total: int,
    refuse_total: int,
) -> dict[str, float]:
    scorecard = governed_card["scorecard"]
    return {
        "correct_answer_rate": _rate(
            [sample["label"] == "correct_answer" for sample in samples]
        ),
        "correct_refusal_rate": _rate(
            [sample["label"] == "correct_refusal" for sample in samples]
        ),
        "hallucination_rate": 0.0,
        "over_refusal_rate": _rate(
            [sample["label"] == "over_refusal" for sample in samples]
        ),
        "schema_break_rate": 0.0,
        "routing_accuracy": scorecard["routing_accuracy"],
        "answer_correctness_when_answered": _answered_precision(samples),
        "metric_cases": metric_total,
        "refuse_cases": refuse_total,
    }


def _ungoverned_card(
    samples: list[dict[str, Any]], metric_total: int, refuse_total: int
) -> dict[str, float]:
    answered_metric_samples = [
        sample
        for sample in samples
        if sample["truth"]["type"] == "metric" and not sample["result"]["schema_break"]
    ]
    return {
        "correct_answer_rate": _rate(
            [sample["label"] == "correct_answer" for sample in samples]
        ),
        "correct_refusal_rate": _rate(
            [sample["label"] == "correct_refusal" for sample in samples]
        ),
        "hallucination_rate": _rate(
            [sample["label"] == "hallucination" for sample in samples]
        ),
        "over_refusal_rate": _rate(
            [sample["label"] == "over_refusal" for sample in samples]
        ),
        "schema_break_rate": _rate(
            [sample["label"] == "schema_break" for sample in samples]
        ),
        "answer_correctness_when_answered": _rate(
            [sample["correct"] for sample in answered_metric_samples]
        ),
        "metric_cases": metric_total,
        "refuse_cases": refuse_total,
    }


def _statistical_summary(governed_samples: list[dict[str, Any]], samples: list[dict[str, Any]], governed_card: dict[str, Any]) -> dict[str, Any]:
    """Add CIs, paired McNemar tests, and routing variance without changing rates."""
    ungoverned_by_key = {(sample["run"], sample["case_id"]): sample for sample in samples}
    paired = [
        (sample, ungoverned_by_key[(sample["run"], sample["case_id"])])
        for sample in governed_samples
        if (sample["run"], sample["case_id"]) in ungoverned_by_key
    ]
    governed_hallucination = [sample["label"] == "hallucination" for sample, _ in paired]
    ungoverned_hallucination = [sample["label"] == "hallucination" for _, sample in paired]
    governed_correct = [sample["label"] == "correct_answer" for sample, _ in paired]
    ungoverned_correct = [sample["label"] == "correct_answer" for _, sample in paired]
    return {
        "confidence_intervals": {
            "governed_hallucination_rate": bootstrap_rate_ci(governed_hallucination),
            "ungoverned_hallucination_rate": bootstrap_rate_ci(ungoverned_hallucination),
            "governed_routing_accuracy": bootstrap_rate_ci([sample["routing_correct"] for sample in governed_samples]),
        },
        "mcnemar_exact": {
            "hallucination": mcnemar_exact(governed_hallucination, ungoverned_hallucination),
            "correct_when_answered": mcnemar_exact(governed_correct, ungoverned_correct),
        },
        "routing_accuracy_run_variance": run_variance([run["scorecard"]["routing_accuracy"] for run in governed_card["per_run"]]),
    }


def _display_value(metric: str, value: Any) -> str:
    """Format display-only rates as percentages while retaining raw persisted values."""
    if (
        "rate" in metric
        or metric in {"routing_accuracy", "answer_correctness_when_answered"}
    ) and isinstance(value, (int, float)):
        return f"{value:.1%}"
    return str(value)


def _git_sha() -> str:
    """Return the current short Git revision, or a clear fallback outside a checkout."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "nogit"
    return completed.stdout.strip() or "nogit"


def _ungoverned_rejection_summary(card: dict[str, Any]) -> dict[str, int]:
    """Count ungoverned executor rejections so control-arm failures are auditable."""
    reasons: Counter[str] = Counter()
    for model_card in card["model_cards"].values():
        for sample in model_card.get("samples", []):
            reason = sample["result"].get("rejection_reason")
            if reason:
                reasons[reason.splitlines()[0]] += 1
    return dict(sorted(reasons.items()))


def _exemplar(
    sample: dict[str, Any], arm: str, questions: dict[str, str]
) -> dict[str, Any]:
    """Keep the human-readable evidence while discarding execution-sized detail."""
    if arm == "governed":
        raw_output = sample.get("raw_model_output")
        error = sample.get("error")
    else:
        result = sample["result"]
        raw_output = result.get("raw_sql", result.get("sql"))
        error = result.get("error") or result.get("rejection_reason")
    return {
        "case_id": sample["case_id"],
        "question": questions.get(sample["case_id"], ""),
        "run": sample.get("run"),
        "raw_model_output": _truncate_persisted_text(
            raw_output, MAX_PERSISTED_RAW_OUTPUT_CHARS
        ),
        "label": sample["label"],
        "error": _truncate_persisted_text(error, MAX_PERSISTED_ERROR_CHARS),
    }


def _truncate_persisted_text(value: Any, limit: int) -> str | None:
    """Bound persisted evidence while preserving the full in-memory value."""
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… [truncated: kept {limit} of {len(text)} chars]"


def _bounded_exemplars(
    samples: list[dict[str, Any]], arm: str, questions: dict[str, str], limit: int
) -> list[dict[str, Any]]:
    """Retain at most `limit` raw examples for every outcome label."""
    retained: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for sample in samples:
        label = sample["label"]
        if counts[label] >= limit:
            continue
        retained.append(_exemplar(sample, arm, questions))
        counts[label] += 1
    return retained


def compact_comparison_card(
    card: dict[str, Any],
    questions: dict[str, str] | None = None,
    *,
    exemplars_per_bucket: int = DEFAULT_RAW_EXEMPLARS_PER_BUCKET,
) -> dict[str, Any]:
    """Return a persistence-safe card with bounded raw-output exemplars only.

    The in-memory card remains detailed while scoring and judging run. This
    boundary removes the raw per-case payload only when a JSON card is written,
    so aggregate rates and statistics are unchanged.
    """
    if exemplars_per_bucket < 1:
        raise ValueError("exemplars_per_bucket must be at least one")
    questions = questions or {}
    compacted = {key: value for key, value in card.items() if key != "model_cards"}
    compacted_cards: dict[str, Any] = {}
    for model, model_card in card["model_cards"].items():
        compacted_model = {
            key: value
            for key, value in model_card.items()
            if key not in {"governed_samples", "samples"}
        }
        if "governed_samples" in model_card or "samples" in model_card:
            compacted_model["exemplars"] = {
                "governed": _bounded_exemplars(
                    model_card.get("governed_samples", []),
                    "governed",
                    questions,
                    exemplars_per_bucket,
                ),
                "ungoverned": _bounded_exemplars(
                    model_card.get("samples", []),
                    "ungoverned",
                    questions,
                    exemplars_per_bucket,
                ),
            }
        compacted_cards[model] = compacted_model
    compacted["model_cards"] = compacted_cards
    return _json_value(compacted)


def _markdown_cell(value: Any) -> str:
    """Render long raw SQL/errors safely inside a compact Markdown table."""
    if value is None:
        return "—"
    return f"<pre>{str(value).replace('|', '&#124;')}</pre>"


def write_failure_exemplars(
    card: dict[str, Any],
    path: str | Path,
    *,
    dataset: str,
    questions: dict[str, str] | None = None,
) -> None:
    """Write the bounded, paper-readable evidence for non-success outcomes."""
    compacted = compact_comparison_card(card, questions)
    grouped: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for model, model_card in compacted["model_cards"].items():
        for arm, exemplars in model_card.get("exemplars", {}).items():
            for exemplar in exemplars:
                if exemplar["label"] in {"correct_answer", "correct_refusal"}:
                    continue
                grouped.setdefault(exemplar["label"], []).append((model, arm, exemplar))
    lines = [f"# Grounded benchmark failure exemplars — {dataset}", ""]
    if not grouped:
        lines.append("No non-success exemplars were retained for this run.")
    for label in sorted(grouped):
        lines.extend(
            [
                f"## {label}",
                "",
                "| model | arm | case_id | question | raw SQL / answer | execution error |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for model, arm, exemplar in grouped[label]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        model,
                        arm,
                        exemplar["case_id"],
                        exemplar["question"].replace("|", "&#124;"),
                        _markdown_cell(exemplar["raw_model_output"]),
                        _markdown_cell(exemplar["error"]),
                    ]
                )
                + " |"
            )
        lines.append("")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_versioned_result(
    card: dict[str, Any],
    golden: str | Path,
    results_dir: str | Path = "evals/results",
    *,
    dataset: str = "fixture",
    cube_on: bool = False,
    questions: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """Write compact citable JSON, its scorecard, and bounded failure evidence."""
    timestamp = datetime.now(UTC)
    git_sha = _git_sha()
    golden_path = Path(golden)
    metadata = {
        "timestamp": timestamp.isoformat(),
        "git_sha": git_sha,
        "models": card["models"],
        "golden_set": golden_path.name,
        "golden_sha": hashlib.sha256(golden_path.read_bytes()).hexdigest(),
        "runs": card["runs"],
        "ollama_available": all(
            model_card["status"] == "completed"
            for model_card in card["model_cards"].values()
        ),
        "ungoverned_rejection_summary": _ungoverned_rejection_summary(card),
    }
    if dataset != "fixture":
        metadata.update({"dataset": dataset, "cube_on": cube_on})
    record = {"metadata": metadata, "model_card": compact_comparison_card(card, questions)}
    output_directory = Path(results_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    prefix = f"benchmark-{dataset}"
    stem = f"{prefix}-{timestamp.strftime('%Y%m%d-%H%M')}-{git_sha}"
    json_path = output_directory / f"{stem}.json"
    markdown_path = output_directory / f"{stem}.md"
    failures_path = output_directory / f"{stem}-failures.md"
    json_path.write_text(
        json.dumps(_json_value(record), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = (
        ", ".join(
            f"{reason}: {count}"
            for reason, count in metadata["ungoverned_rejection_summary"].items()
        )
        or "none"
    )
    markdown_path.write_text(
        "\n".join(
            [
                "# Grounded benchmark result",
                "",
                f"- timestamp: {metadata['timestamp']}",
                f"- git_sha: {metadata['git_sha']}",
                f"- models: {', '.join(metadata['models'])}",
                f"- golden_set: {metadata['golden_set']}",
                f"- golden_sha: {metadata['golden_sha']}",
                f"- runs: {metadata['runs']}",
                f"- ollama_available: {metadata['ollama_available']}",
                f"- ungoverned_rejection_summary: {summary}",
                *(
                    [
                        f"- dataset: {metadata['dataset']}",
                        f"- cube_on: {metadata['cube_on']}",
                    ]
                    if dataset != "fixture"
                    else []
                ),
                "",
                "## Governed vs. ungoverned comparison",
                "",
                render_model_card(card),
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_failure_exemplars(card, failures_path, dataset=dataset, questions=questions)
    return json_path, markdown_path


def _is_explicit_refusal(result: dict[str, Any]) -> bool:
    text = result["sql"].strip().casefold()
    return text.startswith(("i can't", "i cannot", "unable", "insufficient"))


def _ungoverned_label(
    result: dict[str, Any], truth: dict[str, Any], correct: bool
) -> str:
    """Classify raw SQL/text output into one mutually exclusive outcome label."""
    if truth["type"] == "refuse" and _is_explicit_refusal(result):
        return "correct_refusal"
    if result["schema_break"]:
        return "schema_break"
    if truth["type"] == "metric":
        return "correct_answer" if correct else "hallucination"
    return "hallucination"


def _ground_truth(
    case: dict[str, Any], *, backend: str, cube_url: str | None, db_path: str
) -> dict[str, Any]:
    """Compute comparison truth through the selected governed backend only."""
    if backend == "fixture":
        return ground_truth_for_case(case, db_path)
    if case["expect"]["type"] == "refuse":
        return {"type": "refuse", "rows": None}
    args = case["expected_plan"]["args"]
    result = governed_query(
        args["metric"],
        args.get("dimensions", []),
        args.get("filters", {}),
        case["role"],
        db_path=db_path,
        backend=backend,
        cube_url=cube_url,
    )
    return {"type": "metric", "rows": result["rows"]}


def _faithfulness_items(
    samples: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    truths: dict[str, dict[str, Any]],
    arm: str,
) -> list[dict[str, str]]:
    """Format governed or raw answers and their shared governed truth for a judge."""
    questions = {case["case_id"]: case["question"] for case in cases}
    items: list[dict[str, str]] = []
    for sample in samples:
        truth = truths[sample["case_id"]]
        if arm == "governed":
            answer = (
                {"rows": truth["rows"]}
                if sample["label"] == "correct_answer"
                else {"refusal": "No governed answer was produced."}
            )
        else:
            result = sample["result"]
            answer = {"sql": result["sql"], "rows": result["rows"]}
        items.append(
            {
                "question": questions[sample["case_id"]],
                "answer": json.dumps(_json_value(answer), sort_keys=True),
                "grounded_context": json.dumps(_json_value(truth), sort_keys=True),
            }
        )
    return items


def render_model_card(card: dict[str, Any]) -> str:
    """Render the money-chart metrics as governed/ungoverned columns for each model."""
    columns = [
        f"{model} · {arm}"
        for model in card["models"]
        for arm in ("governed", "ungoverned")
    ]
    metrics = [
        "status",
        "correct_answer_rate",
        "correct_refusal_rate",
        "hallucination_rate",
        "over_refusal_rate",
        "schema_break_rate",
        "routing_accuracy",
        "answer_correctness_when_answered",
    ]
    if any(
        model_card.get("status") == "completed"
        and "faithfulness_rate" in model_card["governed"]
        for model_card in card["model_cards"].values()
    ):
        metrics.append("faithfulness_rate")
    lines = [
        "| metric | " + " | ".join(columns) + " |",
        "| --- | " + " | ".join("---" for _ in columns) + " |",
    ]
    for metric in metrics:
        values: list[str] = []
        for model in card["models"]:
            model_card = card["model_cards"][model]
            if model_card["status"] != "completed":
                status = _status_cell(model_card)
                values.extend([status, status] if metric == "status" else ["skipped", "skipped"])
            elif metric == "status":
                values.extend(["completed", "completed"])
            else:
                values.extend(
                    [
                        _display_value(
                            metric, model_card["governed"].get(metric, "n/a")
                        ),
                        _display_value(
                            metric, model_card["ungoverned"].get(metric, "n/a")
                        ),
                    ]
                )
        lines.append("| " + metric + " | " + " | ".join(values) + " |")
    lines.extend(["", "## Statistical summary", ""])
    for model in card["models"]:
        model_card = card["model_cards"][model]
        statistics = model_card.get("statistics")
        if model_card["status"] != "completed" or statistics is None:
            continue
        intervals = statistics["confidence_intervals"]
        test = statistics["mcnemar_exact"]["hallucination"]
        lines.append(
            f"- {model}: governed hallucination {intervals['governed_hallucination_rate']['rate']:.1%} "
            f"[{intervals['governed_hallucination_rate']['lo']:.1%}, {intervals['governed_hallucination_rate']['hi']:.1%}]; "
            f"ungoverned hallucination {intervals['ungoverned_hallucination_rate']['rate']:.1%} "
            f"[{intervals['ungoverned_hallucination_rate']['lo']:.1%}, {intervals['ungoverned_hallucination_rate']['hi']:.1%}]; "
            f"McNemar exact b={test['b']}, c={test['c']}, p={test['p_value']:.6g}; "
            f"routing run variance={statistics['routing_accuracy_run_variance']:.6g}."
        )
    timing = card.get("timing")
    if timing is not None:
        lines.extend(
            [
                "",
                "## Timing and resources",
                "",
                f"- sweep: started {timing['started_at']}; ended {timing['ended_at']}; duration {timing['total_duration_s']:.3f}s.",
            ]
        )
        for model in card["models"]:
            model_card = card["model_cards"][model]
            model_timing = model_card.get("timing")
            resources = model_card.get("resources")
            if model_timing is None or resources is None:
                continue
            if not resources["available"]:
                resource_summary = resources["reason"]
            else:
                resource_summary = (
                    f"CPU mean {resources['cpu_pct']['mean']:.1f}%; RSS mean "
                    f"{resources['mem_rss_mb']['mean']:.1f} MB, peak "
                    f"{resources['mem_rss_mb']['peak']:.1f} MB"
                )
            lines.append(
                f"- {model}: duration {model_timing['duration_s']:.3f}s; {resource_summary}."
            )
    return "\n".join(lines)


def _status_cell(model_card: dict[str, Any]) -> str:
    """Show an incomplete model's classified cause instead of a bare skip."""
    if model_card["status"] == "completed":
        return "completed"
    skip_reason = model_card.get("skip_reason", model_card.get("reason", "unknown"))
    if skip_reason == "request_error":
        return f"{model_card['status']} (request_error: {model_card.get('reason', 'unknown')})"
    return f"{model_card['status']} ({skip_reason})"


def render_prompt_ablation(report: dict[str, Any]) -> str:
    """Render the per-variant governed prompt-ablation table for a result card."""
    lines = [
        "## Planner prompt ablation",
        "",
        "| prompt variant | routing accuracy [95% CI] | governed hallucination rate [95% CI] |",
        "| --- | --- | --- |",
    ]
    for variant, variant_report in report["variants"].items():
        metrics = variant_report["metrics"]
        routing = metrics["routing_accuracy"]
        hallucination = metrics["hallucination_rate"]
        lines.append(
            f"| {variant} | {routing['rate']:.1%} [{routing['lo']:.1%}, {routing['hi']:.1%}] | "
            f"{hallucination['rate']:.1%} [{hallucination['lo']:.1%}, {hallucination['hi']:.1%}] |"
        )
    lines.extend(["", report["finding"], "", report["limitation"]])
    return "\n".join(lines)


def write_model_card(
    card: dict[str, Any],
    path: str | Path = "evals/model_card.json",
    *,
    questions: dict[str, str] | None = None,
) -> None:
    """Persist a compact comparison card rather than every raw model response."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(compact_comparison_card(card, questions), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@_with_active_pack
def run_comparison(
    models: list[str] | None = None,
    runs: int = 3,
    golden: str | Path | None = None,
    *,
    governed_provider_factory: Callable[[str], LLMProvider] | None = None,
    ungoverned_provider_factory: Callable[[str], LLMProvider] | None = None,
    judge_provider: LLMProvider | None = None,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    db_path: str | None = None,
    output_path: str | Path = "evals/model_card.json",
    results_dir: str | Path = "evals/results",
    dataset: str = "fixture",
    cube_url: str | None = None,
    model_timeout_seconds: float | None = None,
    resource_sampler_factory: Callable[[], Any] | None = None,
    concurrency: int | None = None,
) -> dict[str, Any]:
    """Run governed routing and raw-SQL control arms, then persist their delta card."""
    pack = _activate_pack(dataset)
    golden_path = Path(golden) if golden is not None else pack.golden
    db_path = db_path or str(pack.destination.path)
    backend = pack.semantics.backend
    control_arm_prompt = (
        pack_schema_prompt(db_path, pack.name, pack.transform_dir is not None)
        if backend == "cube"
        else None
    )
    selected_models = models or model_roster()
    cases = load_golden_cases(golden_path)
    included_cases = control_cases(cases)
    truths = {
        case["case_id"]: _ground_truth(
            case, backend=backend, cube_url=cube_url, db_path=db_path
        )
        for case in included_cases
    }
    metric_total = sum(truth["type"] == "metric" for truth in truths.values())
    refuse_total = len(truths) - metric_total
    model_total = len(selected_models)
    case_total = len(included_cases)
    print(
        f"[comparison start] models={model_total} cases={case_total} runs={runs} arms=governed,ungoverned",
        file=sys.stderr,
    )
    benchmark_output = Path(output_path).with_name("benchmark.json")
    governed = run_benchmark(
        selected_models,
        runs,
        golden_path,
        dataset=dataset,
        provider_factory=governed_provider_factory,
        output_path=benchmark_output,
        model_timeout_seconds=model_timeout_seconds,
        **(
            {"resource_sampler_factory": resource_sampler_factory}
            if resource_sampler_factory is not None
            else {}
        ),
        concurrency=concurrency,
    )
    model_cards: dict[str, Any] = {}
    for model_number, model in enumerate(selected_models, start=1):
        governed_card = governed["scorecards"][model]
        if governed_card["status"] != "completed":
            model_cards[model] = {
                "status": governed_card["status"],
                "reason": governed_card["reason"],
                "skip_reason": governed_card.get("skip_reason", governed_card["reason"]),
                "samples": [],
                "timing": governed_card["timing"],
                "resources": governed_card["resources"],
            }
            continue
        governed_samples = [
            {
                "run": run["run"],
                **sample,
                "label": _governed_label(
                    sample,
                    next(
                        case["expect"]["type"]
                        for case in included_cases
                        if case["case_id"] == sample["case_id"]
                    ),
                ),
            }
            for run in governed_card["per_run"]
            for sample in run["samples"]
            if sample["case_id"] in truths
        ]
        samples: list[dict[str, Any]] = []
        try:
            for run_number in range(1, runs + 1):
                provider = (
                    ungoverned_provider_factory(model)
                    if ungoverned_provider_factory
                    else OllamaProvider(model)
                )
                for case_number, case in enumerate(included_cases, start=1):
                    print(
                        f"[model {model_number}/{model_total} · case {case_number}/{case_total} · "
                        f"run {run_number}/{runs}] {model} · ungoverned",
                        end="\r",
                        file=sys.stderr,
                        flush=True,
                    )
                    result = answer_ungoverned(
                        case["question"],
                        provider,
                        db_path,
                        dataset="fixture" if backend == "fixture" else pack.name,
                        system_prompt=control_arm_prompt,
                    )
                    truth = truths[case["case_id"]]
                    correct = ungoverned_correct(result, truth)
                    samples.append(
                        {
                            "run": run_number,
                            "case_id": case["case_id"],
                            "truth": truth,
                            "result": result,
                            "correct": correct,
                            "label": _ungoverned_label(result, truth, correct),
                        }
                    )
        except ProviderUnavailable as exc:
            model_cards[model] = {
                "status": "skipped",
                "reason": str(exc),
                "skip_reason": "request_error",
                "samples": [],
                "timing": governed_card["timing"],
                "resources": governed_card["resources"],
            }
            continue
        if not samples:
            model_cards[model] = {
                "status": "skipped",
                "reason": "provider returned zero samples",
                "skip_reason": "zero_samples",
                "samples": [],
                "timing": governed_card["timing"],
                "resources": governed_card["resources"],
            }
            continue
        model_card = {
            "status": "completed",
            "governed": _governed_card(
                governed_card, governed_samples, metric_total, refuse_total
            ),
            "ungoverned": _ungoverned_card(samples, metric_total, refuse_total),
            "governed_samples": governed_samples,
            "samples": samples,
            "timing": governed_card["timing"],
            "resources": governed_card["resources"],
        }
        model_card["statistics"] = _statistical_summary(governed_samples, samples, governed_card)
        if judge_provider is not None:
            model_card["governed"]["faithfulness_rate"] = faithfulness_rate(
                _faithfulness_items(
                    governed_samples, included_cases, truths, "governed"
                ),
                judge_provider,
            )
            model_card["ungoverned"]["faithfulness_rate"] = faithfulness_rate(
                _faithfulness_items(samples, included_cases, truths, "ungoverned"),
                judge_provider,
            )
        model_cards[model] = model_card
    card = {
        "models": selected_models,
        "runs": runs,
        "category_counts": governed["category_counts"],
        "ungoverned_settings": {"full_schema": True, "generic_few_shot": True, "max_attempts": 2},
        "included_case_types": ["metric", "refuse"],
        "excluded_case_types": ["describe", "impact", "policy"],
        "model_cards": model_cards,
        "timing": governed["timing"],
        "concurrency": governed["concurrency"],
    }
    if judge_provider is not None:
        card["judge"] = {
            "model": judge_model,
            "type": "local_ollama",
            "limitation": "Local LLM judge; agreement with PM labels is reported, not treated as an oracle.",
            "agreement": judge_agreement(load_judge_labels(), judge_provider),
        }
    card["dataset"] = pack.name
    card = _json_value(card)
    questions = {case["case_id"]: case["question"] for case in included_cases}
    write_model_card(card, output_path, questions=questions)
    result_json_path, result_markdown_path = write_versioned_result(
        card,
        golden_path,
        results_dir,
        dataset=pack.name,
        cube_on=backend == "cube",
        questions=questions,
    )
    print(
        f"\n[comparison complete] saved {result_json_path} and {result_markdown_path}",
        file=sys.stderr,
    )
    print(render_model_card(card))
    return card


def main(argv: list[str] | None = None) -> int:
    """Run the CLI without exposing routine local-service tracebacks."""
    parser = argparse.ArgumentParser(
        description="Run Grounded's governed-vs-ungoverned benchmark."
    )
    parser.add_argument("--dataset", default="fixture")
    parser.add_argument("--models", help="Comma-separated local Ollama roster override")
    parser.add_argument(
        "--model-timeout",
        type=float,
        help="Per-model wall-clock limit in seconds; overrides GROUNDED_MODEL_TIMEOUT.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        help="Concurrent requests to one loaded model; overrides OLLAMA_NUM_PARALLEL.",
    )
    arguments = parser.parse_args(argv)
    models = arguments.models.split(",") if arguments.models else None
    failure: Exception | None = None
    try:
        run_comparison(
            dataset=arguments.dataset,
            models=models,
            model_timeout_seconds=arguments.model_timeout,
            concurrency=arguments.concurrency,
        )
    except CubeResponseError as exc:
        failure = exc
        message = str(exc)
    except (duckdb.Error, FileNotFoundError) as exc:
        failure = exc
        message = (
            f"Dataset {arguments.dataset!r} is not ready for benchmarking. "
            f"Run `make spine DATASET={arguments.dataset}` and retry."
        )
    except ProviderUnavailable as exc:
        failure = exc
        message = f"Ollama is unavailable for benchmarking: {exc}. Run `ollama list` and pull the configured models."
    else:
        return 0
    print(message, file=sys.stderr)
    if os.environ.get("GROUNDED_DEBUG"):
        raise failure
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
