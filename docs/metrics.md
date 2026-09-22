# Evaluation taxonomy and rates

The benchmark asks: **For declared analytical tasks, what does a governed
interface change about answer correctness, useful coverage, policy enforcement,
and inspectability, and what does it cost?** It is a system comparison,
catalog plus governed tools versus schema plus SQL. It does not isolate the
mechanism.

The evals report a failure taxonomy and routing coverage as distributions; the
governed answer-level rate is one dimension among four, each with its
denominator.

## Four scored dimensions

| Dimension | Question | Denominator |
| --- | --- | --- |
| `answer_correctness` | Did the executed rows match an independent expected answer? | Answered, in-catalog cases with independent truth. |
| `interface_compliance` | Was the produced declared call or raw SQL output well formed for its arm? | Applicable attempted outputs. |
| `policy_compliance` | Did the result respect applicable scope and masking requirements? | Cases with an applicable policy obligation. |
| `evidence_completeness` | Is the required definition, policy record, verification, and lineage evidence present and matched to execution? | Governed metric answers requiring evidence. |

`hallucination_rate` in the free-form-SQL sense does not apply to the governed
arm, which cannot author SQL. The governed arm's answer-level failure is a
valid-but-wrong selection (`wrong_answer`), and that rate is measured, not
assumed.

## Summary labels

| Label | Meaning |
| --- | --- |
| `correct_answer` | An executed in-catalog answer matched independent truth. |
| `wrong_answer` | An executed answer differed from independent truth, including a response to a required refusal. |
| `correct_refusal` | A request that should be refused was refused. |
| `over_refusal` | An answerable request was refused. |
| `schema_break` | A raw SQL output was rejected or could not execute. Governed `schema_break` is not applicable because it cannot author SQL. |

## Reported rates

Every rate carries a numerator and denominator. A conditional rate is `null`
when its denominator is zero rather than being presented as a perfect score.

| Rate | Definition |
| --- | --- |
| `answer_correctness_when_answered` | Correct answers divided by correct plus wrong answers. |
| `wrong_answer_rate` | Wrong answers divided by the relevant scored cases. |
| `over_refusal_rate` | Over-refusals divided by answerable cases. |
| `correct_refusal_rate` | Correct refusals divided by required-refusal cases. |
| `routing_accuracy` | Exact declared-plan match among answerable governed proposals. |
| `schema_break_rate` | Raw SQL schema breaks divided by applicable raw attempts. |

## Runs=3 five-pack summary

The table reports the observed range across the nine local models. The
in-catalog denominator is fixed within each pack for wrong answers and
evidence; the conditional correct denominator changes with answered cases.
Coverage makes that second denominator visible as answered / all, and refused
/ unscorable is its complement over all. The full per-model numerators and
denominators are in
[benchmarks.md](benchmarks.md).

| Pack | In-catalog cases / model | Coverage (answered / all) | Refused / unscorable (÷ all) | Gov. correct / answered | Gov. wrong / all | Gov. evidence / all | Raw SQL correct / answered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AdventureWorks | 213 | 15.5%–100.0% | 0.0%–84.5% | 0.0%–94.3% | 5.6%–40.8% | 7.0%–94.4% | 4.7%–22.5% |
| TPC-H | 228 | 50.0%–100.0% | 0.0%–50.0% | 10.5%–98.7% | 1.3%–47.4% | 50.0%–98.7% | 0.0% |
| Spider world_1 | 93 | 93.5%–100.0% | 0.0%–6.5% | 79.3%–100.0% | 0.0%–19.4% | 83.9%–100.0% | 0.0%–13.3% |
| BIRD california_schools | 69 | 65.2%–100.0% | 0.0%–34.8% | 60.0%–100.0% | 0.0%–39.1% | 39.1%–78.3% | 0.0%–15.4% |
| Fixture | 30 | 10.0%–100.0% | 0.0%–90.0% | 80.0%–100.0% | 0.0%–20.0% | 10.0%–100.0% | 0.0%–12.5% or n/a |

The fixture has small denominators and is deterministic. Its range validates
the harness surface rather than a real-workload claim.

A model can have a low raw answer-error rate only because it schema-breaks or
refuses almost everything. A valid governed call can still select the wrong
metric, period, dimension, or scope. These distinctions are why the four
dimensions must be read together.
