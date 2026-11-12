# Product and engineering risk register

Scope: English-only, local-first, synthetic/public-mock documentation prototype.
These ratings are engineering triage, not a clinical risk assessment. No risk
rating authorizes use with real patients. Owners below are the responsible
implementation role for this checklist, not a qualified clinical reviewer.

| ID | Risk | Severity | Current control / evidence | Unresolved action | Owner | State |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | Audio or transcript source corruption creates unsupported downstream facts. | P0 | SHA-256 asset checks, immutable transcript versions, exact quote/span validation, proposal integrity tests. | Add end-to-end corruption injection for retranscription, proposal, approval, and export; bind the full run to a fresh acceptance receipt. | AI agent | In progress |
| R-02 | A clinically important fact is omitted from the draft without a warning. | P0 | Deterministic coverage and contradiction checks; failure-inclusive clinical challenge fixtures. | Expand unseen independent review set; external clinicians are unavailable, so sensitivity remains unknown. | AI agent; clinical owner needed | Blocked: independent labels |
| R-03 | A medication name, dose, route, timing, allergy, or action is bound to the wrong drug. | P0 | Typed relationship checks and synthetic medication-swap tests. | Validate on independently adjudicated cases and preserve medication-specific false alarms and misses. | AI agent; clinical reviewers needed | Blocked: independent labels |
| R-04 | Diarization assigns speech to the wrong person or clinician role. | P1 | Speaker turns retain unknown/unconfirmed states; two-channel and role checks exist. | Run independent turn/role scoring and physical microphone checks; no hardware device is identified. | AI agent; device owner needed | Blocked: hardware/reviewers |
| R-05 | Credentials, tokens, audio, or note text leak through logs, reports, fixtures, or source control. | P0 | Error redaction, secret scans, content-free audit events, ignored local configuration and data. | Re-run secret and data scans on the final source and archived CI artifacts; document any findings. | AI agent | In progress |
| R-06 | An export leaks an unapproved or corrupted note to an external recipient. | P0 | Exact-version approval gates, export hash verification, escaped formats, tenant/clinician access tests. | Exercise end-to-end revocation, stale approval, tenant mismatch, and tampered export at the release commit. | AI agent | In progress |
| R-07 | A stale approval remains usable after its source transcript or note changes. | P0 | Immutable versions and current-source approval checks with stale-source tests. | Add complete interruption/retry/source-edit/approval race matrix to the acceptance receipt. | AI agent | In progress |
| R-08 | A deployment exposes a local demo or enables hosted processing without intended controls. | P1 | Loopback defaults, offline mode, configuration validation, container checks. | Complete exact-SHA hosted CI and an operator deployment review; no institution or deployment owner is assigned. | AI agent; deployment owner needed | Blocked: external deployment review |

## Review rules

- P0 means a failure can directly corrupt source, misstate a clinical fact,
  expose protected information, or bypass approval. Model output cannot waive
  a P0 finding.
- `In progress` does not mean verified. Only the master task ledger can record
  completion, and only with an exact-commit, hash-bound test receipt.
- Synthetic cases exercise software behavior. They do not estimate clinical
  sensitivity, real-world harm, or user acceptance.
- Clinical review, deployment approval, and real-patient authorization remain
  external prerequisites. The project currently authorizes none of them.
