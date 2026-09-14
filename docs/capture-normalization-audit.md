# Truncated-capture normalization audit (receipt)

This is the receipt for the full-result audit referenced in the README, whitepaper,
and benchmark report. It exists so the claim "no published label changed under the
corrected comparison" can be inspected, not just asserted. It is my own audit result,
not an independently reproduced one.

## Why the audit was run

For results larger than the stored row preview, the offline scorer falls back to a
stored exact hash rather than a rounding-normalized comparison (`captured_rows_match`
in `evals/offline_scoring.py`). A raw or governed result that differed from the
expected answer only in decimal precision could, in principle, have been scored wrong
by that fallback. The audit re-executes every attempt to recover its full result and
re-scores it with the declared two-decimal normalized comparison, then compares the
new label to the published one.

## Method

- **No model inference.** Only already-captured artifacts were replayed: for the raw
  arm, the stored `ungoverned.raw_sql` run against the pinned local DuckDB; for the
  governed arm, the stored `produced_plan` re-run through the resolver under the
  captured case role (Cube up one pack at a time).
- **Comparison reused from the scorer.** Expected rows come from the independent
  truth path (`independent_rows`); both arms are normalized to the declared
  two-decimal precision and compared with the scorer's multiset `rows_match`.
- **Raw-arm script:** `reexec_audit.py` (repo root), runnable offline with only
  the local `data/<pack>.duckdb` files. **Governed arm:** the scorer's recovery path
  (`--recover-governed`), added in the recovery hardening.

## Inputs (capture SHA-256, from each result card)

| Pack | Capture | SHA-256 |
| --- | --- | --- |
| AdventureWorks | `aw-final-r3.jsonl` | `5126f0442794070b995ab018ffb68d28b0763a745750a9d6aa6dd40a89afca16` |
| TPC-H | `tpch-final-r3.jsonl` | `d4c7214083533d814bd3520b648bbda62e7548d2a0fc928def8874a8a1166f7c` |
| Spider world_1 | `spider-final-r3.jsonl` | `5704a2c179f689e377193c13b8aaf1452bea01cbce78e98ae630669e5815348c` |
| BIRD california_schools | `bird-final-r3.jsonl` | `01faf49e6ae8eef026e3e4ba283e750222c354b15d5b0c5dc583638343f9f9dc` |
| Fixture | `fixture-final-r3.jsonl` | `22ab8c857a43b34de5d11541e88f22f30b85d9fc23eb9acdf92398e3e9c590d1` |

Dataset tree snapshots matched the values recorded on the cards before any replay.

## Raw arm result

| Pack | Records checked | Truncated (fallback path) | Label changes (wrong↔correct) | Re-exec errors |
| --- | ---: | ---: | ---: | ---: |
| AdventureWorks | 1812 | 93 | 0 | 276 |
| TPC-H | 1914 | 198 | 0 | 294 |
| Spider world_1 | 801 | 0 | 0 | 60 |
| BIRD california_schools | 594 | 111 | 0 | 255 |
| Fixture | 210 | 0 | 0 | 90 |
| **Total** | **5331** | **402** | **0** | **975** |

The 975 re-exec errors are stored raw SQL that does not execute against the pinned
database at all (invented columns such as `line_total`, `category`, `part_type`,
`extended_price`; MySQL backtick quoting; non-existent functions such as `dateadd`).
The script counts these separately and excludes them from the old-vs-new label
comparison, so this audit does not by itself re-establish their prior labels. They
are non-executing SQL, so they could not have produced a correct answer in the
published run either; the capable models (phi4, qwen2.5:14b) produced zero such
errors.

## Governed arm result

Re-scored via the scorer's recovery path across the four packs with governed
fallback records (Fixture had none). Governed replays with zero recovery errors:
AdventureWorks 15, TPC-H 270, BIRD 495, Spider 0. **Label changes: 0** on every pack;
every governed per-model correct-when-answered and wrong-answer rate is identical to
the pre-audit scoring.

## Conclusion and scope

Across both arms, no published label changed under the full-result normalized
comparison. This confirms the published numbers against the specific precision /
truncation concern. It does not by itself establish every other aspect of benchmark
validity, and it is a past-result check. At the time of this audit the default
comparison could still use the exact-hash fallback; the reject-unscorable hardening
has since landed, so the default path now marks an unresolved truncated result
unscorable (both arms) rather than comparing it by hash, and full-result recovery is
opt-in (`--recover-raw`, `--recover-governed`). Root-cause classification of raw
failures remains heuristic.

Revision: audited against the
reviewed scoring outputs. Reviewed repository snapshot: `3c06624`.
