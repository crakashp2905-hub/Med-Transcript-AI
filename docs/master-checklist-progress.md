# Master checklist progress

This is an engineering progress record for the 369-task in-house ledger at
[`evaluation/master-task-ledger.json`](../evaluation/master-task-ledger.json).
The JSON file is the tracking source. A feature present in the repository is
not automatically a verified task: the task needs a passing, hash-matched
receipt tied to its source commit. `python -m services.master_ledger` checks
those claims. As imported, all 369 entries are `not_started`; this means
**unreconciled in the new ledger**, not that the repository has no features.

## Starting evidence

- The clean starting source was `b93937756427d1ae86adf847c680ed52c187b9ed`.
- [`master-baseline-b939377.json`](../evaluation/reports/master-baseline-b939377.json)
  records the original ledger hash, 94 hashed local model files, six
  development dataset manifests, frozen report hashes, local tool versions,
  and the latest CI failure. Reserved acceptance cohort contents were not
  read during baseline capture.
- The prior source-bound offline report, [`v21`](../evaluation/reports/offline-acceptance-v21.json),
  passed its seven software checks at `b939377`. It does not prove current
  post-format source, 5% ASR accuracy, or independent clinical performance.
- The latest pre-remediation GitHub Actions run at `b939377` failed because
  the Python format gate found 429 unformatted files; the optional ASR test
  job was cancelled during installation. Its [run record](https://github.com/crakashp2905-hub/Med-Transcript-AI/actions/runs/43099092013)
  remains a failure.

## Reconciliation order

1. Keep the supplied ledger and baseline receipt immutable. Audit each task
   against code, tests, report hashes, and the source commit.
2. Restore all five hosted CI jobs at one exact SHA. Local Ruff format and
   lint pass after the mechanical formatting and follow-up fixes; local mypy
   has not completed and is not counted as a pass.
   Commit `796a9d9` moves a pinned Ruff format check ahead of full backend
   dependency installation. Local Ruff 0.15.13 format/lint passed on the
   current working source; hosted run results for the pushed SHA are not
   available from GitHub in this environment.
   A broad local regression run finished with 585 passed and six skipped,
   but concurrent source commits landed during its execution, so this run is
   not used as an exact-commit task receipt.
3. Attach task-specific receipts to the ledger. A task can become `verified`
   only when its test result is passing, its report hash matches, and the
   report states the same source commit. Failed and blocked statuses remain
   visible.
4. Implement remaining P0 tasks, then P1 and P2 in dependency order. Keep
   original benchmark reports untouched and publish versioned successors.

## Section 00 triage

These are audit candidates, not ledger status promotions. Their checks and
source receipts must be mapped individually before the JSON changes.

| Task | Repository finding | Next evidence needed |
| --- | --- | --- |
| 00-01 | Local baseline receipt captures the clean starting SHA and permitted asset digests. | Commit-bound capture test and current CI result. |
| 00-02 | README and offline scope ADR state English-only, clinician-supervised documentation assistance. | Exact source and scope assertion. |
| 00-03 | Baseline records local model and development manifest hashes. | Artifact policy test against the frozen inventory. |
| 00-04 | `STRICT_OFFLINE=1` now enables Python network denial and rejects Google sign-in and hosted drafting configuration. | Commit-bound tests and a native-process containment boundary remain required for a stronger guarantee. |
| 00-05 | The historical four-dimension matrix remains for old reports. A five-tier assessment is now used by the readiness CLI and new offline acceptance reports. | Exact-commit CI and research evidence are still needed before promoting higher tiers. |
| 00-06 | [`master-implementation-matrix-v1.json`](../evaluation/reports/master-implementation-matrix-v1.json) maps all 369 ledger rows to owner, priority, evidence and blocker fields. It retains `not_started` statuses and marks task-level dependency edges as unmapped. Numbered section order is a planning hint only. | Manually audit task-level dependency edges and populate receipt fields only from exact-commit evidence. |
| 00-07 | A local threat model exists. | Explicit risk register with the requested eight risks and owners. |
| 00-08 | Selection policy fixes maximum normalized WER at 5%. | Gate test and immutable denominator evidence. |
| 00-09 | README and evaluation reports distinguish developer cases from clinical gold. | UI and paper copy audit. |
| 00-10 | Reserved acceptance material exists. | Access-control and no-peeking audit without running inference on it. |
| 00-11 | Safety gates exist. | Explicit P0/P1/P2 taxonomy and model-waiver denial tests. |
| 00-12 | New master ledger validator rejects missing or mismatched receipts. | Exact-commit test report for the validator. |
| 00-13 | Ledger validator admits `blocked_missing_asset`. | Missing-artifact path test and task receipt. |
| 00-14 | Deterministic drafting mode exists. | Feature-flag regression test tied to a commit. |
| 00-15 | Offline acceptance refuses overwriting prior versions. | Retention test and hashes of historical outputs. |
| 00-16 | Limitations appear in README and reports. | Cross-surface UI/export/model-card consistency check. |

## Research and release constraints

The frozen scope-separated comparison reports Omi at 8.70% normalized WER
on 118 selected short clips and 13.05% on three full mock consultations;
both fail the unchanged 5% gate. The paired MedDistract development scopes
also fail. These are different denominators and must not be merged into a
single quality claim. See
[`scope-separated-baselines-v1.json`](../evaluation/reports/scope-separated-baselines-v1.json).

Developer-authored clinical challenge cases and rule checks are not
independently adjudicated clinician labels. No qualified reviewers, live
Google Workspace registration, real hardware recording validation, or
real-patient pilot approval are currently evidenced. Paid model calls and
missing-asset downloads are out of scope. Real-patient release remains
unauthorized.

## Task-specific status update

`MTA-04-06` is now `implemented` in the source ledger. Its receipt binds the
metric code, endpoint registry and passing tests to source commit
`7c6102499980a0a8095ffc3a403809e3da23f69e` in
[`master-task-mta-04-06-7c61024.json`](../evaluation/reports/master-task-mta-04-06-7c61024.json).
The current ledger audit accepts the receipt. The metric implementation does
not establish clinical validity; the 5% normalized WER gate remains unchanged.

## Current execution matrix

[`master-implementation-matrix-v1.json`](../evaluation/reports/master-implementation-matrix-v1.json)
was generated from source commit `4b2d82106423046cff9b841a386f5d20ea4a6ea7`.
Its SHA-256 is `09a46f134d2d16793f39431c1deffbb790fe01a379db9d7c022d43b14ca64d4a`;
the raw ledger SHA-256 is
`0a146204187c9e70ca420bf6997db5e3519a154bd607dcfaf7745bea4ac34f2b`.
All 369 entries remain `not_started` because this matrix is an organization
artifact, not task completion evidence. Clinical release remains unauthorized.
