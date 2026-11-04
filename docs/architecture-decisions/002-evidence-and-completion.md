# ADR 002 — Evidence-backed task completion

The supplied checklist contains 247 uniquely identified tasks. The machine-readable ledger is `evaluation/reports/engineering-task-status.json`; `python -m services.engineering_status --write-scorecard` verifies hashes and generates the scorecard. Only `verified` counts toward the completed percentage. `implemented`, `failed`, `blocked_external_evidence`, `blocked_missing_local_artifact` and `not_started` remain separate.

Every verified entry requires existing hash-matching evidence, named tests, limitations and a source/provenance reference inside the evidence artifact. Changed or missing evidence invalidates the count. A report with skipped checks cannot be represented as a fully passing run. Prefer versioned acceptance reports; never replace a failed/interrupted report with a repaired one. Mutable scorecards are projections, not immutable research evidence.

P0 release blockers include unsafe auto-approval, identity/tenant leakage, missing audit attribution and corrupted evidence. P1 denotes incomplete important engineering/research functionality; P2 denotes presentation/ergonomics improvements. P0 failures block an engineering verification claim irrespective of an aggregate score.

Historical metrics and text references remain in their original dataset scopes. Paired clean/distracted recordings share foreground consultations; they are not independent patients. Exact source-note preservation is not clinical note accuracy, simulated review time is not clinician time, and synthetic transport duration is not natural consultation ASR performance.
