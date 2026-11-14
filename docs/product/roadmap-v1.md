# Product roadmap v1

**Planning style:** dependency gates, not calendar promises. No phase authorizes real-patient use.

| Gate | Objective | Exit evidence | Dependencies / stop conditions |
|---|---|---|---|
| A — Reproducible engineering baseline | Keep offline checks, exact-commit reports and preserved benchmark failures current. | Clean exact-source acceptance run with machine-readable hashes and all failures retained. | Stop on failed CI, stale receipt, missing data provenance, or changed gate without explicit approval. |
| B — Accuracy and attribution development | Improve full-conversation ASR and speaker handling; evaluate medication, negation, omission and verification. | Per-consultation/role/clinical-term metrics on development data; independent challenge results when reviewers are available; unchanged 5% WER admission gate. | Local assets only. No promotion from synthetic-only evaluation to clinical validity. |
| C — Workflow and hardware validation | Exercise 20–30-minute capture/review, interruption/retry/source edits, channel configurations, and physical audio equipment. | Exact-commit browser/workflow results and device/OS/interface/channel test record with safe fallback. | Physical test waits for identified hardware; long-session tests must preserve source and reject stale approvals. |
| D — Independent evaluation and operational readiness | Establish an independent acceptance cohort and complete security, retention, identity, support and recovery review. | Qualified reviewer/adjudication records; owner-signed deployment and privacy/security evidence; measured latency/cost and clinician correction time. | Blocked until institution and qualified reviewers are available. |
| E — Scoped pilot decision | Decide whether a supervised pilot can be proposed to a specific institution. | Intended-use and jurisdiction review, clinical owner approval, privacy/security/IT approval, prospective protocol and rollback plan. | No pilot, patient data, or production release before required owners authorize it. |

Order is based on engineering dependencies and documented unknowns, not customer interviews, revenue projections, or a delivery-date commitment. See [backlog](product-backlog-v1.md) and [risk register](risk-register.md).
