# Evaluation taxonomy and rates

Each comparison sample has one mutually exclusive outcome. The governed and ungoverned arms share the same golden question and governed truth.

| Label | Meaning |
| --- | --- |
| `correct_answer` | An answerable request produced rows equal to governed truth. |
| `correct_refusal` | A request expected to be refused was refused. |
| `hallucination` | A non-schema-breaking answer is not equal to governed truth, or an answer was supplied where refusal was required. |
| `over_refusal` | An answerable request was safely refused or failed routing. |
| `schema_break` | Raw SQL was rejected or could not run against the declared schema. |

## Reported rates

| Rate | Definition |
| --- | --- |
| `hallucination_rate` | Fraction of all samples labeled `hallucination`. For the governed arm it is structurally zero because only validated metric execution can produce an answer. |
| `routing_accuracy` | Fraction of planner proposals that exactly match the golden governed plan. It applies to the governed arm. |
| `faithfulness_rate` | Fraction of answers a strict local judge marks supported by the governed context. The judge result is reported with agreement against hand labels. |
| `over_refusal_rate` | Fraction of answerable requests that were refused or failed to route. It measures lost coverage, not a wrong numeric answer. |
| `schema_break_rate` | Fraction of raw-SQL samples rejected by the parser or database. It is separate from hallucination because no answer executed. |
| `answer_correctness_when_answered` | Correct-answer fraction conditional on an answer reaching execution. For governed execution, any validated answer comes from the governed metric backend. |

Rates must be read together. A model can have low hallucination only because it schema-breaks or refuses almost everything; a 0% safety rate alone is not a coverage claim. The benchmark adds bootstrap confidence intervals, exact paired McNemar tests, and per-run routing variance to the rate table.
