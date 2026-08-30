# Thin agent

This agent defaults to a deterministic, keyword-based `plan(question) -> ToolCall`
seam and calls only Grounded's `harness/` governed tool layer. It does not receive
a SQL connection or raw tables. The governed tools own the definitions, policy
enforcement, verification, audit trail, and lineage citation.

The deterministic planner keeps the default demo and CI reproducible. The optional
LLM planner uses a provider only to propose one JSON tool call. Before execution,
`agent.llm_planner` validates the call against the six MCP-governed tools and
their schemas. Invalid JSON, an unknown tool, undeclared metric dimensions or
filters, and extra arguments all become a refusal. The model cannot receive a
database connection or widen Grounded's governed surface.

`query_customers` is a governed customer-directory read. It masks email by
default and unmasks it only for the asserted `analyst_pii` or `admin` caller
role. The role comes from the calling session, not from model-proposed tool
arguments, so the model cannot choose or elevate its own identity.

Run the seeded demo with:

```bash
python scripts/seed_duckdb.py
python -m agent.run "What was revenue last month by product category?"
```

## Optional local Ollama evaluation

Ollama is optional and is never used by CI. Install and start it locally, then
pull the small default model:

```bash
ollama serve
ollama pull llama3.2
```

Run the existing golden set through the guarded LLM planner and write separate
traces. This performs no hosted call and records zero local model cost:

```bash
python - <<'PY'
from evals.runner import run_evals
from models.provider import OllamaProvider

run_evals(
    planner="llm",
    provider=OllamaProvider(),
    traces_path="evals/ollama_traces.jsonl",
)
PY
python - <<'PY'
from evals.metrics import compute_scorecard
from evals.scorecard import render_scorecard
from evals.trace import read_traces

print(render_scorecard(compute_scorecard(read_traces("evals/ollama_traces.jsonl"))))
PY
```

Use the resulting trace file with the scorecard workflow to compare the guarded
local planner. The expected experiment is that an LLM can route the July revenue
paraphrase while every emitted call still passes the same tool guardrail.
