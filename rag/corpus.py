"""Load the small, curated prose corpus used for definition retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from packlib import active_pack

_ROOT = Path(__file__).resolve().parents[1]
_FLAGSHIP_POLICY_HEADINGS = {
    "The boundary this makes explicit (your thesis, in code)",
    "Governance, verification, audit (the three words that make it \"harness\" not \"wrapper\")",
}


def _paragraph_chunks(path: Path, headings: set[str] | None = None) -> list[dict[str, str]]:
    """Return prose paragraphs keyed by their nearest Markdown heading."""
    chunks: list[dict[str, str]] = []
    heading = path.stem.replace("_", " ").title()
    paragraph: list[str] = []
    in_code_block = False

    def add_paragraph() -> None:
        text = " ".join(line.strip() for line in paragraph).strip()
        if text and (headings is None or heading in headings):
            chunks.append({"doc": str(path.relative_to(_ROOT)), "heading": heading, "text": text})
        paragraph.clear()

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            add_paragraph()
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if line.startswith("#"):
            add_paragraph()
            heading = line.lstrip("#").strip()
            continue
        if line.strip():
            paragraph.append(line)
        else:
            add_paragraph()
    add_paragraph()
    return chunks


def _semantic_description_chunks() -> list[dict[str, str]]:
    """Return one definition chunk for every declared governed metric."""
    chunks: list[dict[str, str]] = []
    pack = active_pack()
    for path in sorted(pack.semantics.metrics if pack.semantics else ()):
        definition: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "metric" not in definition:
            continue
        chunks.append(
            {
                "doc": str(path.relative_to(_ROOT)),
                "heading": definition["label"],
                "text": definition["description"],
            }
        )
    return chunks


def load_corpus() -> list[dict[str, str]]:
    """Load metric descriptions and the curated governance/data-dictionary prose."""
    return [
        *_semantic_description_chunks(),
        *_paragraph_chunks(_ROOT / "docs" / "contracts.md"),
        *_paragraph_chunks(
            _ROOT / "docs" / "flagship.md",
            headings=_FLAGSHIP_POLICY_HEADINGS,
        ),
        *_paragraph_chunks(_ROOT / "rag" / "data_dictionary.md"),
    ]
