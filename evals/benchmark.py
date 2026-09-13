"""Run Golden v2 routing/refusal benchmarks through Grounded's governed planner."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import wraps
from math import ceil
from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from agent.agent import _execute_tool_call, plan
from agent.llm_planner import parse_model_output, system_prompt, validate_model_output
from agent.ungoverned import answer_ungoverned, pack_schema_prompt
from evals.offline_scoring import _aliases_for_metric, rows_content_hash
from evals.resources import ResourceSampler, process_resource_sampler
from evals.roster import model_roster
from evals.routing import score_routing
from models.provider import (
    LLMProvider,
    OllamaProvider,
    ProviderUnavailable,
)
from packlib import Pack, load_pack
from semantics.loader import load_expanded_definition

DEFAULT_MODEL_TIMEOUT_SECONDS = 30 * 60
DEFAULT_REQUEST_CONCURRENCY = 2
CAPTURE_ROW_PREVIEW_LIMIT = 50
_GOVERNED_TOOLS = {
    "list_metrics",
    "describe_metric",
    "query_metric",
    "query_customers",
    "check_policy",
    "impact_of",
    "search_docs",
    "refuse",
}
GOLDEN_CATEGORIES = frozenset(
    {
        "total",
        "by_dimension",
        "by_multi_dimension",
        "ranking",
        "paraphrase",
        "role_governed",
        "describe",
        "impact",
        "policy",
        "refuse_out_of_scope",
        "refuse_adversarial",
    }
)


class ModelTimeout(RuntimeError):
    """Raised when one model exceeds its benchmark wall-clock budget."""


class CaptureWriter:
    """Append bounded model-inference records so scoring can run offline later."""

    def __init__(self, path: str | Path, metadata: dict[str, Any]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self.path.write_text(
            _json_line(
                {
                    "record_type": "manifest",
                    "schema_version": 3,
                    "row_hash_normalization": "declared_metric_two_decimal_v1",
                    **metadata,
                }
            ),
            encoding="utf-8",
        )

    def write(self, record: dict[str, Any]) -> None:
        with self._lock, self.path.open("a", encoding="utf-8") as capture_file:
            capture_file.write(_json_line({"record_type": "case", **_compact_capture_record(record)}))


def _json_safe(value: Any) -> Any:
    """Make captured runtime artifacts JSON serializable without truncating them."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _json_line(record: dict[str, Any]) -> str:
    return json.dumps(_json_safe(record), sort_keys=True) + "\n"


def _capture_metric_aliases(record: dict[str, Any]) -> dict[str, str]:
    plan = record.get("expected_plan")
    metric = plan.get("args", {}).get("metric") if isinstance(plan, dict) else None
    return _aliases_for_metric(metric) if isinstance(metric, str) else {}


def _capture_metric(record: dict[str, Any]) -> str | None:
    plan = record.get("expected_plan")
    metric = plan.get("args", {}).get("metric") if isinstance(plan, dict) else None
    return metric if isinstance(metric, str) else None


def _compact_rows(
    rows: Any, *, aliases: dict[str, str], metric: str | None
) -> tuple[list[dict[str, Any]] | None, int | None, str | None]:
    """Retain a bounded preview and a full-result fingerprint for offline scoring."""
    if not isinstance(rows, list):
        return None, None, None
    return (
        rows[:CAPTURE_ROW_PREVIEW_LIMIT],
        len(rows),
        rows_content_hash(rows, alias_map=aliases, metric=metric),
    )


def _compact_capture_record(record: dict[str, Any]) -> dict[str, Any]:
    """Remove duplicate full results while preserving exact comparison metadata."""
    compact = dict(record)
    aliases = _capture_metric_aliases(record)
    metric = _capture_metric(record)

    governed_rows, governed_count, governed_hash = _compact_rows(
        compact.get("governed_rows"), aliases=aliases, metric=metric
    )
    compact["governed_rows"] = governed_rows
    compact["governed_row_count"] = governed_count
    compact["governed_rows_hash"] = governed_hash
    compact.pop("governed_response", None)

    raw = compact.get("ungoverned")
    raw = dict(raw) if isinstance(raw, dict) else None
    raw_rows_source = raw.get("rows") if raw is not None else compact.get("ungoverned_rows")
    ungoverned_rows, ungoverned_count, ungoverned_hash = _compact_rows(
        raw_rows_source, aliases=aliases, metric=metric
    )
    compact["ungoverned_rows"] = ungoverned_rows
    compact["ungoverned_row_count"] = ungoverned_count
    compact["ungoverned_rows_hash"] = ungoverned_hash
    if raw is not None:
        raw["rows"] = ungoverned_rows
        raw["row_count"] = ungoverned_count
        raw["rows_hash"] = ungoverned_hash
        compact["ungoverned"] = raw
    return compact


def resolve_model_timeout_seconds(explicit: float | None = None) -> float:
    """Resolve CLI, environment, then default per-model timeout precedence."""
    value = (
        explicit
        if explicit is not None
        else os.environ.get("GROUNDED_MODEL_TIMEOUT", DEFAULT_MODEL_TIMEOUT_SECONDS)
    )
    try:
        seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "GROUNDED_MODEL_TIMEOUT must be a positive number of seconds"
        ) from exc
    if seconds <= 0:
        raise ValueError("model timeout must be a positive number of seconds")
    return seconds


def resolve_request_concurrency(explicit: int | None = None) -> int:
    """Resolve CLI, environment, then conservative request-concurrency default."""
    value = (
        explicit
        if explicit is not None
        else os.environ.get("OLLAMA_NUM_PARALLEL", DEFAULT_REQUEST_CONCURRENCY)
    )
    try:
        concurrency = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("OLLAMA_NUM_PARALLEL must be a positive integer") from exc
    if concurrency < 1:
        raise ValueError("request concurrency must be a positive integer")
    return concurrency


@contextmanager
def _model_timeout(seconds: float):
    """Interrupt the current model evaluation without affecting later models."""
    if seconds <= 0:
        raise ValueError("model_timeout_seconds must be positive")

    def expire(_signum: int, _frame: Any) -> None:
        raise ModelTimeout("timeout")

    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _release_model(model: str) -> None:
    """Ask the local Ollama service to unload a timed-out model before continuing."""
    subprocess.run(
        ["ollama", "stop", model], capture_output=True, check=False, text=True
    )


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


def load_golden_cases(golden: str | Path) -> list[dict[str, Any]]:
    """Load a PM-authored golden set and reject plans outside the public surface."""
    with Path(golden).open(encoding="utf-8") as golden_file:
        cases = yaml.safe_load(golden_file)
    if not isinstance(cases, list):
        raise TypeError("Golden set must be a list of cases.")
    for case in cases:
        plan = case.get("expected_plan", {}) if isinstance(case, dict) else {}
        tool = plan.get("tool") if isinstance(plan, dict) else None
        args = plan.get("args") if isinstance(plan, dict) else None
        if tool not in _GOVERNED_TOOLS or not isinstance(args, dict):
            raise ValueError(
                f"Golden case {case.get('case_id', '<unknown>')!r} targets an undeclared tool."
            )
        if tool == "query_metric":
            metric = args.get("metric")
            if not isinstance(metric, str):
                raise ValueError(
                    f"Golden case {case['case_id']!r} has no declared metric."
                )
            try:
                load_expanded_definition(metric)
            except FileNotFoundError as exc:
                raise ValueError(
                    f"Golden case {case['case_id']!r} targets undeclared metric {metric!r}."
                ) from exc
    return cases


def select_cases(
    cases: list[dict[str, Any]], case_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    """Select an explicit bounded subset without silently dropping a requested case."""
    if case_ids is None:
        return cases
    selected = [case for case in cases if case["case_id"] in case_ids]
    found = {case["case_id"] for case in selected}
    missing = sorted(case_ids - found)
    if missing:
        raise ValueError(f"Unknown case IDs: {', '.join(missing)}")
    if not selected:
        raise ValueError("At least one case must be selected for collection.")
    return selected


def validate_categorized_golden(cases: list[dict[str, Any]]) -> dict[str, int]:
    """Validate PM-authored categorized cases against the active pack surface."""
    counts: Counter[str] = Counter()
    for case in cases:
        case_id = case.get("case_id", "<unknown>")
        category = case.get("category")
        if category not in GOLDEN_CATEGORIES:
            raise ValueError(
                f"Golden case {case_id!r} has unknown category {category!r}."
            )
        expected = case.get("expected_plan")
        expect = case.get("expect")
        if not isinstance(expect, dict) or not isinstance(expected, dict):
            raise TypeError(
                f"Golden case {case_id!r} must declare expected_plan and expect."
            )
        validated = validate_model_output(expected)
        if validated != expected:
            raise ValueError(
                f"Golden case {case_id!r} is outside the active pack surface."
            )
        tool = expected["tool"]
        expected_type = expect.get("type")
        if (tool == "refuse") != (expected_type == "refuse"):
            raise ValueError(
                f"Golden case {case_id!r} has inconsistent refusal expectation."
            )
        if tool == "check_policy" and expect.get("decision") not in {"allow", "mask"}:
            raise ValueError(
                f"Golden policy case {case_id!r} needs allow or mask decision."
            )
        counts[category] += 1
    if not any(case["expected_plan"]["tool"] == "refuse" for case in cases):
        raise ValueError(
            "Categorized golden set must include at least one refusal case."
        )
    return dict(sorted(counts.items()))


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(1, ceil(len(ordered) * percentile / 100)) - 1]


def _rate(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _schema_valid(candidate: Any) -> bool:
    """Measure whether extracted model output names a real governed call."""
    return (
        isinstance(candidate, dict)
        and set(candidate) == {"tool", "args"}
        and candidate.get("tool") in _GOVERNED_TOOLS
        and isinstance(candidate.get("args"), dict)
    )


def _plan_schema_valid(plan_candidate: Any) -> bool:
    """Apply the same public tool-envelope check to the deterministic baseline."""
    return (
        isinstance(plan_candidate, dict)
        and set(plan_candidate) == {"tool", "args"}
        and plan_candidate.get("tool") in _GOVERNED_TOOLS
        and isinstance(plan_candidate.get("args"), dict)
    )


def _provider_plan(
    question: str, provider: LLMProvider, planner_prompt: str | None = None
) -> tuple[dict[str, Any], str, dict[str, Any] | None, bool]:
    """Capture one raw provider response, then pass that exact response through the guardrail."""
    raw_response = provider.complete(planner_prompt or system_prompt(), question)
    parsed_plan = parse_model_output(raw_response)
    produced_plan = validate_model_output(parsed_plan)
    return produced_plan, raw_response, parsed_plan, _schema_valid(parsed_plan)


def _run_card(samples: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [
        sample for sample in samples if sample["expected_plan"]["tool"] != "refuse"
    ]
    refusal_expected = [
        sample for sample in samples if sample["expected_plan"]["tool"] == "refuse"
    ]
    latencies = [sample["latency_ms"] for sample in samples]
    return {
        "routing_accuracy": _rate([sample["routing_correct"] for sample in answerable]),
        "appropriate_refusal_rate": _rate(
            [sample["produced_plan"]["tool"] == "refuse" for sample in refusal_expected]
        ),
        "over_refusal_rate": _rate(
            [sample["produced_plan"]["tool"] == "refuse" for sample in answerable]
        ),
        "schema_compliance_rate": _rate([sample["schema_valid"] for sample in samples]),
        "latency_ms": {
            "p50": _nearest_rank(latencies, 50),
            "p95": _nearest_rank(latencies, 95),
        },
    }


def _model_scorecard(model: str, per_run: list[dict[str, Any]]) -> dict[str, Any]:
    all_samples = [sample for run in per_run for sample in run["samples"]]
    return {
        "status": "completed",
        "model": model,
        "scorecard": _run_card(all_samples),
        "per_run": [
            {
                "run": run["run"],
                "scorecard": _run_card(run["samples"]),
                "samples": run["samples"],
            }
            for run in per_run
        ],
    }


def _capture_governed_execution(
    produced_plan: dict[str, Any],
    case: dict[str, Any],
    pack: Pack,
    *,
    db_path: str,
    cube_url: str | None,
) -> dict[str, Any]:
    """Execute the model's guarded call through the same seam the agent uses."""
    if produced_plan["tool"] == "refuse":
        return {
            "governed_executed": False,
            "governed_rows": None,
            "policy_decisions": [],
            "evidence": None,
            "governed_execution_error": None,
        }
    try:
        response = _execute_tool_call(
            produced_plan,
            case["role"],
            backend=pack.semantics.backend,
            cube_url=cube_url,
            db_path=db_path,
        )
    except Exception as exc:  # noqa: BLE001 - capture any execution failure for later scoring.
        return {
            "governed_executed": False,
            "governed_rows": None,
            "policy_decisions": [],
            "evidence": None,
            "governed_execution_error": f"{type(exc).__name__}: {exc}",
        }
    evidence = {
        "metric_definition": response.get("metric_definition"),
        "verification": response.get("verification"),
        "verify_status": response.get("verify_status"),
        "lineage_citation": response.get("lineage_citation"),
        "doc_citation": response.get("doc_citation"),
    }
    return {
        "governed_executed": True,
        "governed_rows": response.get("answer_rows"),
        "policy_decisions": response.get("policy_applied", []),
        "evidence": evidence,
        "governed_execution_error": None,
    }


def _capture_ungoverned_execution(
    case: dict[str, Any],
    provider: LLMProvider,
    pack: Pack,
    *,
    db_path: str,
    control_prompt: str | None,
) -> dict[str, Any]:
    """Capture the same raw-SQL control attempt used by the current comparison."""
    result = answer_ungoverned(
        case["question"],
        provider,
        db_path,
        dataset="fixture" if pack.semantics.backend == "fixture" else pack.name,
        system_prompt=control_prompt,
    )
    return {
        "ungoverned_sql": result.get("sql"),
        "ungoverned_rows": result.get("rows"),
        "ungoverned_error": result.get("error") or result.get("rejection_reason"),
        "ungoverned": result,
    }


def _captured_sample(
    sample: dict[str, Any],
    case: dict[str, Any],
    pack: Pack,
    *,
    provider: LLMProvider | None,
    db_path: str,
    cube_url: str | None,
    control_prompt: str | None,
) -> dict[str, Any]:
    """Attach execution evidence to one planning sample without scoring it."""
    captured = {
        **sample,
        "question": case["question"],
        "role": case["role"],
        "category": case.get("category"),
        "expect": case["expect"],
        **_capture_governed_execution(
            sample["produced_plan"], case, pack, db_path=db_path, cube_url=cube_url
        ),
    }
    if provider is None:
        return {
            **captured,
            "ungoverned_sql": None,
            "ungoverned_rows": None,
            "ungoverned_error": "not collected for deterministic baseline",
            "ungoverned": None,
        }
    return {
        **captured,
        **_capture_ungoverned_execution(
            case, provider, pack, db_path=db_path, control_prompt=control_prompt
        ),
    }


def _deterministic_run(
    cases: list[dict[str, Any]],
    progress: Callable[[int], None],
    *,
    pack: Pack | None = None,
    db_path: str | None = None,
    cube_url: str | None = None,
    capture_writer: CaptureWriter | None = None,
    model: str = "deterministic",
    run: int = 1,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for case_number, case in enumerate(cases, start=1):
        progress(case_number)
        started = time.perf_counter()
        produced_plan = plan(case["question"])
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        sample = {
            "case_id": case["case_id"],
            "expected_plan": case["expected_plan"],
            "produced_plan": produced_plan,
            "raw_model_output": None,
            "parsed_plan": produced_plan,
            "routing_correct": score_routing(produced_plan, case["expected_plan"]),
            "schema_valid": _plan_schema_valid(produced_plan),
            "refused": produced_plan["tool"] == "refuse",
            "latency_ms": latency_ms,
        }
        if capture_writer is not None and pack is not None and db_path is not None:
            sample = _captured_sample(
                sample,
                case,
                pack,
                provider=None,
                db_path=db_path,
                cube_url=cube_url,
                control_prompt=None,
            )
            capture_writer.write({"model": model, "run": run, **sample})
        samples.append(sample)
    return samples


def _provider_run(
    cases: list[dict[str, Any]],
    provider: LLMProvider,
    progress: Callable[[int], None],
    planner_prompt: str | None = None,
    concurrency: int = 1,
    *,
    pack: Pack | None = None,
    db_path: str | None = None,
    cube_url: str | None = None,
    capture_writer: CaptureWriter | None = None,
    model: str = "",
    run: int = 1,
) -> list[dict[str, Any]]:
    """Run one model over a case batch, preserving case order after parallel calls."""
    control_prompt = (
        pack_schema_prompt(db_path, pack.name, pack.transform_dir is not None)
        if capture_writer is not None
        and pack is not None
        and db_path is not None
        and pack.semantics.backend == "cube"
        else None
    )

    def evaluate(case_number: int, case: dict[str, Any]) -> dict[str, Any]:
        progress(case_number)
        started = time.perf_counter()
        produced_plan, raw_model_output, parsed_plan, schema_valid = _provider_plan(
            case["question"], provider, planner_prompt
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        sample = {
            "case_id": case["case_id"],
            "expected_plan": case["expected_plan"],
            "produced_plan": produced_plan,
            "raw_model_output": raw_model_output,
            "parsed_plan": parsed_plan,
            "routing_correct": score_routing(produced_plan, case["expected_plan"]),
            "schema_valid": schema_valid,
            "refused": produced_plan["tool"] == "refuse",
            "latency_ms": latency_ms,
        }
        if capture_writer is not None and pack is not None and db_path is not None:
            sample = _captured_sample(
                sample,
                case,
                pack,
                provider=provider,
                db_path=db_path,
                cube_url=cube_url,
                control_prompt=control_prompt,
            )
            capture_writer.write({"model": model, "run": run, **sample})
        return sample

    if concurrency == 1:
        return [
            evaluate(case_number, case) for case_number, case in enumerate(cases, 1)
        ]
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(evaluate, case_number, case)
            for case_number, case in enumerate(cases, 1)
        ]
        return [future.result() for future in futures]


def render_comparison(benchmark: dict[str, Any]) -> str:
    """Render scorecard metrics as rows and completed/skipped models as columns."""
    models = benchmark["models"]
    metrics = [
        ("status", lambda card: card["status"]),
        ("routing_accuracy", lambda card: card["scorecard"]["routing_accuracy"]),
        (
            "appropriate_refusal_rate",
            lambda card: card["scorecard"]["appropriate_refusal_rate"],
        ),
        ("over_refusal_rate", lambda card: card["scorecard"]["over_refusal_rate"]),
        (
            "schema_compliance_rate",
            lambda card: card["scorecard"]["schema_compliance_rate"],
        ),
        ("latency_ms.p50", lambda card: card["scorecard"]["latency_ms"]["p50"]),
        ("latency_ms.p95", lambda card: card["scorecard"]["latency_ms"]["p95"]),
    ]
    lines = [
        (
            "Routing signal only — not answer quality. Answer-level scoring is the "
            "separate offline report (`evals.compare --capture-path`)."
        ),
        "",
        "| metric | " + " | ".join(models) + " |",
        "| --- | " + " | ".join("---" for _ in models) + " |",
    ]
    for name, value_for in metrics:
        values: list[str] = []
        for model in models:
            card = benchmark["scorecards"][model]
            if name == "status":
                values.append(_status_cell(card))
            elif card["status"] == "completed":
                value = value_for(card)
                values.append(
                    f"{value:.1%}"
                    if "rate" in name or name == "routing_accuracy"
                    else str(value)
                )
            else:
                values.append("skipped")
        lines.append("| " + name + " | " + " | ".join(values) + " |")
    return "\n".join(lines)


def _status_cell(card: dict[str, Any]) -> str:
    """Render a non-success model state with its actionable classification."""
    if card["status"] == "completed":
        return "completed"
    skip_reason = card.get("skip_reason", card.get("reason", "unknown"))
    if skip_reason == "request_error":
        return f"{card['status']} (request_error: {card.get('reason', 'unknown')})"
    return f"{card['status']} ({skip_reason})"


def write_benchmark(
    benchmark: dict[str, Any], path: str | Path = "evals/benchmark.json"
) -> None:
    """Persist scorecards without the full governed raw-response payload."""
    compacted = {key: value for key, value in benchmark.items() if key != "scorecards"}
    compacted_scorecards: dict[str, Any] = {}
    for model, scorecard in benchmark["scorecards"].items():
        compacted_scorecard = {
            key: value for key, value in scorecard.items() if key != "per_run"
        }
        compacted_scorecard["per_run"] = [
            {
                "run": run["run"],
                "scorecard": _run_card(run["samples"]),
                "sample_count": len(run["samples"]),
            }
            for run in scorecard.get("per_run", [])
        ]
        compacted_scorecards[model] = compacted_scorecard
    compacted["scorecards"] = compacted_scorecards
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(compacted, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


@_with_active_pack
def run_benchmark(
    models: list[str] | None = None,
    runs: int = 3,
    golden: str | Path | None = None,
    *,
    dataset: str = "fixture",
    provider_factory: Callable[[str], LLMProvider] | None = None,
    output_path: str | Path = "evals/benchmark.json",
    model_timeout_seconds: float | None = None,
    planner_prompt: str | None = None,
    monotonic_clock: Callable[[], float] = time.perf_counter,
    wall_clock: Callable[[], datetime] | None = None,
    resource_sampler_factory: Callable[[], ResourceSampler] = process_resource_sampler,
    concurrency: int | None = None,
    capture_path: str | Path | None = None,
    db_path: str | None = None,
    cube_url: str | None = None,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Benchmark routing, optionally retaining complete execution captures for later scoring."""
    if runs < 1:
        raise ValueError("runs must be at least 1")
    model_timeout_seconds = resolve_model_timeout_seconds(model_timeout_seconds)
    concurrency = resolve_request_concurrency(concurrency)
    wall_clock = wall_clock or (lambda: datetime.now(UTC))
    sweep_started_at = wall_clock()
    sweep_started = monotonic_clock()
    pack = _activate_pack(dataset)
    golden_path = Path(golden) if golden is not None else pack.golden
    cases = select_cases(load_golden_cases(golden_path), case_ids)
    category_counts = (
        validate_categorized_golden(cases)
        if all("category" in case for case in cases)
        else {}
    )
    selected_models = models or model_roster()
    db_path = db_path or str(pack.destination.path)
    capture_writer = (
        CaptureWriter(
            capture_path,
            {
                "dataset": pack.name,
                "golden_path": str(golden_path),
                "models": selected_models,
                "runs": runs,
                "started_at": sweep_started_at.isoformat(),
            },
        )
        if capture_path is not None
        else None
    )
    scorecards: dict[str, Any] = {}
    model_total = len(selected_models)
    case_total = len(cases)
    print(
        f"[benchmark start] models={model_total} cases={case_total} runs={runs} arm=governed",
        file=sys.stderr,
    )
    for model_number, model in enumerate(selected_models, start=1):
        per_run: list[dict[str, Any]] = []
        model_started = monotonic_clock()
        sampler = resource_sampler_factory()
        sampler.start()
        try:
            timeout = (
                _model_timeout(model_timeout_seconds)
                if model != "deterministic"
                else nullcontext()
            )
            with timeout:
                for run_number in range(1, runs + 1):

                    def progress(
                        case_number: int,
                        current_model_number: int = model_number,
                        current_run_number: int = run_number,
                        current_model: str = model,
                    ) -> None:
                        print(
                            f"[model {current_model_number}/{model_total} · case {case_number}/{case_total} · "
                            f"run {current_run_number}/{runs}] {current_model} · governed",
                            end="\r",
                            file=sys.stderr,
                            flush=True,
                        )

                    samples = (
                        _deterministic_run(
                            cases,
                            progress,
                            pack=pack,
                            db_path=db_path,
                            cube_url=cube_url,
                            capture_writer=capture_writer,
                            model=model,
                            run=run_number,
                        )
                        if model == "deterministic"
                        else _provider_run(
                            cases,
                            (
                                provider_factory(model)
                                if provider_factory
                                else OllamaProvider(model)
                            ),
                            progress,
                            planner_prompt,
                            concurrency,
                            pack=pack,
                            db_path=db_path,
                            cube_url=cube_url,
                            capture_writer=capture_writer,
                            model=model,
                            run=run_number,
                        )
                    )
                    per_run.append({"run": run_number, "samples": samples})
        except ProviderUnavailable as exc:
            scorecards[model] = {
                "status": "skipped",
                "model": model,
                "reason": str(exc),
                "skip_reason": "request_error",
                "per_run": [],
            }
        except ModelTimeout:
            _release_model(model)
            print(
                f"\n[benchmark incomplete] {model} timed out; increase "
                "GROUNDED_MODEL_TIMEOUT or pass --model-timeout before retrying.",
                file=sys.stderr,
            )
            scorecards[model] = {
                "status": "incomplete",
                "model": model,
                "reason": "timeout",
                "skip_reason": "timeout",
                "per_run": [],
            }
        else:
            if any(run["samples"] for run in per_run):
                scorecards[model] = _model_scorecard(model, per_run)
            else:
                scorecards[model] = {
                    "status": "skipped",
                    "model": model,
                    "reason": "provider returned zero samples",
                    "skip_reason": "zero_samples",
                    "per_run": [],
                }
        finally:
            scorecards[model]["timing"] = {
                "duration_s": monotonic_clock() - model_started,
            }
            scorecards[model]["resources"] = sampler.stop()

    sweep_ended_at = wall_clock()
    benchmark = {
        "models": selected_models,
        "runs": runs,
        "concurrency": concurrency,
        "scorecards": scorecards,
        "category_counts": category_counts,
        "timing": {
            "started_at": sweep_started_at.isoformat(),
            "ended_at": sweep_ended_at.isoformat(),
            "total_duration_s": monotonic_clock() - sweep_started,
        },
    }
    benchmark["dataset"] = pack.name
    if capture_writer is not None:
        benchmark["capture_path"] = str(capture_writer.path)
    write_benchmark(benchmark, output_path)
    print(
        f"\n[benchmark complete] models={model_total} cases={case_total} runs={runs} arm=governed",
        file=sys.stderr,
    )
    print(render_comparison(benchmark))
    return benchmark


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Grounded's governed routing benchmark."
    )
    parser.add_argument("--dataset", default="fixture")
    parser.add_argument("--models", help="Comma-separated local Ollama roster override")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model-timeout", type=float)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument(
        "--capture-path",
        help="Write complete per-case JSONL captures here for offline scoring.",
    )
    parser.add_argument(
        "--case-ids",
        help="Comma-separated case IDs for a bounded collection run.",
    )
    parser.add_argument("--db-path")
    parser.add_argument("--cube-url")
    arguments = parser.parse_args()
    run_benchmark(
        dataset=arguments.dataset,
        models=arguments.models.split(",") if arguments.models else None,
        runs=arguments.runs,
        model_timeout_seconds=arguments.model_timeout,
        concurrency=arguments.concurrency,
        capture_path=arguments.capture_path,
        case_ids=set(arguments.case_ids.split(",")) if arguments.case_ids else None,
        db_path=arguments.db_path,
        cube_url=arguments.cube_url,
    )
