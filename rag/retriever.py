"""Dependency-free lexical retrieval over Grounded's curated prose corpus."""

from __future__ import annotations

import re
from collections import Counter
from math import log, sqrt

from rag.corpus import load_corpus

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


def _vector(tokens: list[str], document_frequency: Counter[str], corpus_size: int) -> dict[str, float]:
    counts = Counter(tokens)
    if not counts:
        return {}
    return {
        token: count * (log((1 + corpus_size) / (1 + document_frequency[token])) + 1)
        for token, count in counts.items()
    }


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    numerator = sum(weight * right.get(token, 0.0) for token, weight in left.items())
    left_length = sqrt(sum(weight * weight for weight in left.values()))
    right_length = sqrt(sum(weight * weight for weight in right.values()))
    return numerator / (left_length * right_length) if left_length and right_length else 0.0


def search(query: str, k: int = 3) -> list[dict[str, str | float]]:
    """Return the top ``k`` prose chunks by deterministic TF-IDF cosine score."""
    if k <= 0:
        return []
    corpus = load_corpus()
    document_tokens = [
        _tokens(f"{chunk['heading']} {chunk['text']}")
        for chunk in corpus
    ]
    document_frequency: Counter[str] = Counter(
        token for tokens in document_tokens for token in set(tokens)
    )
    query_vector = _vector(_tokens(query), document_frequency, len(corpus))
    ranked: list[dict[str, str | float]] = []
    for chunk, tokens in zip(corpus, document_tokens, strict=True):
        score = _cosine(query_vector, _vector(tokens, document_frequency, len(corpus)))
        ranked.append({**chunk, "score": round(score, 6)})
    return sorted(
        ranked,
        key=lambda chunk: (-float(chunk["score"]), str(chunk["doc"]), str(chunk["heading"])),
    )[:k]
