# Grounded benchmark result

> **⚠ Superseded (2026-09-08).** The governed columns in this card (`hallucination_rate` 0.0%, `answer_correctness_when_answered` 100%, and the McNemar comparisons) were produced by construction, not measured: the governed arm was scored on routing and its answers were not executed and checked. These governed figures are withdrawn and must not be cited as answer-quality evidence. The ungoverned columns reflect executed raw-SQL runs. Corrected cards will replace this after the 061 rerun.

- timestamp: 2026-08-21T20:25:43.596398+00:00
- git_sha: 558021a
- models: phi4
- golden_set: golden.yml
- golden_sha: 08bad2ccce2a34c563d40d956d720b2980e544cfc31a76faf0c23fcea856915a
- runs: 3
- ollama_available: False
- ungoverned_rejection_summary: none
- dataset: adventureworks
- cube_on: True

## Governed vs. ungoverned comparison

| metric | phi4 · governed | phi4 · ungoverned |
| --- | --- | --- |
| status | skipped | skipped |
| correct_answer_rate | skipped | skipped |
| correct_refusal_rate | skipped | skipped |
| hallucination_rate | skipped | skipped |
| over_refusal_rate | skipped | skipped |
| schema_break_rate | skipped | skipped |
| routing_accuracy | skipped | skipped |
| answer_correctness_when_answered | skipped | skipped |

## Statistical summary


## Timing and resources

- sweep: started 2026-08-21T20:00:24.783657+00:00; ended 2026-08-21T20:25:43.592157+00:00; duration 1518.800s.
- phi4: duration 1517.588s; CPU mean 0.3%; RSS mean 21.5 MB, peak 128.3 MB.
