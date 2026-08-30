# Retrieval for meaning questions

This package indexes a deliberately small corpus: declared metric descriptions,
the governance prose in `docs/contracts.md` and the policy sections of
`docs/flagship.md`, and `rag/data_dictionary.md`. It is not a source of
governed numbers. Numeric questions continue through `query_metric` and the
metric tree.

`rag.retriever.search` uses deterministic, dependency-free TF-IDF cosine
retrieval. A returned chunk has its source document and heading so the agent can
cite it as `[doc#heading]`.

An optional future upgrade can replace the lexical vector construction with
Ollama embeddings while keeping the same corpus and result shape. That upgrade
must remain a retrieval-only change: it must not bypass governed metric queries
or turn retrieved prose into numeric evidence.
