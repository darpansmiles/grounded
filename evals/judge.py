"""Faithfulness judging for evaluation answers against governed context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from models.provider import LLMProvider

JUDGE_SYSTEM_PROMPT = """You are a strict faithfulness judge for governed data answers.
Decide whether every claim and number in the answer under test is supported by
the grounded context. Do not use outside knowledge. Return exactly one JSON
object with this shape and no markdown:
{"faithful": true, "reason": "brief evidence-based explanation"}
Use faithful=false when any claim or number is unsupported."""
DEFAULT_JUDGE_MODEL = "qwen2.5:14b"
JUDGE_LABELS_PATH = Path(__file__).with_name("judge_labels.yml")


@dataclass
class StubJudge:
    """Deterministic judge that selects a canned verdict by answer substring."""

    verdicts: dict[str, dict[str, Any] | str]
    default: str = "unparseable"

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        del system, temperature
        answer = user.partition("Answer under test:\n")[2].partition("\n\nGrounded context:")[0]
        for substring, verdict in self.verdicts.items():
            if substring in answer:
                return json.dumps(verdict) if isinstance(verdict, dict) else verdict
        return self.default


def judge_faithfulness(
    question: str, answer: str, grounded_context: str, provider: LLMProvider
) -> dict[str, bool | str]:
    """Return a defensive structured verdict for an answer against governed context."""
    request = (
        f"Question:\n{question}\n\n"
        f"Answer under test:\n{answer}\n\n"
        f"Grounded context:\n{grounded_context}"
    )
    response = provider.complete(JUDGE_SYSTEM_PROMPT, request)
    try:
        verdict = json.loads(response)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"faithful": False, "reason": "unparseable judge output"}
    if (
        not isinstance(verdict, dict)
        or set(verdict) != {"faithful", "reason"}
        or type(verdict["faithful"]) is not bool
        or not isinstance(verdict["reason"], str)
    ):
        return {"faithful": False, "reason": "unparseable judge output"}
    return {"faithful": verdict["faithful"], "reason": verdict["reason"]}


def faithfulness_rate(items: list[dict[str, str]], provider: LLMProvider) -> float:
    """Judge each supplied item and return the fraction faithful."""
    if not items:
        return 0.0
    faithful = sum(
        judge_faithfulness(
            item["question"], item["answer"], item["grounded_context"], provider
        )["faithful"]
        for item in items
    )
    return faithful / len(items)


def load_judge_labels(path: str | Path = JUDGE_LABELS_PATH) -> list[dict[str, Any]]:
    """Load PM's hand-labeled faithfulness guard set."""
    with Path(path).open(encoding="utf-8") as labels_file:
        labels = yaml.safe_load(labels_file)
    if not isinstance(labels, list) or not labels:
        raise ValueError("Judge labels must be a non-empty list")
    for item in labels:
        required = {"case_id", "pack", "question", "answer", "ground_truth", "faithful", "note"}
        if not isinstance(item, dict) or not required <= set(item) or type(item["faithful"]) is not bool:
            raise ValueError("Each judge label must include the declared case fields")
    return labels


def judge_agreement(labels: list[dict[str, Any]], provider: LLMProvider) -> dict[str, Any]:
    """Report local-judge agreement with PM hand labels; the judge remains non-oracular."""
    verdicts = [
        judge_faithfulness(item["question"], item["answer"], item["ground_truth"], provider)
        for item in labels
    ]
    matches = sum(verdict["faithful"] == item["faithful"] for item, verdict in zip(labels, verdicts, strict=True))
    return {"labeled_cases": len(labels), "agreement_rate": matches / len(labels), "verdicts": verdicts}
