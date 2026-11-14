# Technical debt and evidence gaps v1

This register tracks known constraints at planning time. “Debt” includes missing evidence and operational prerequisites; it does not imply every gap can be solved in code.

| ID | Debt / gap | Impact | Current state | Closure evidence | Owner / dependency |
|---|---|---|---|---|---|
| TD-01 | Eligible ASR models miss the 5% normalized-WER admission gate. | High | Benchmark failures preserved; no qualifying model established. | New full-conversation run with coverage/timestamp checks and unchanged gate. | Engineering; local candidate assets |
| TD-02 | Clinical quality is not independently established. | High | Synthetic challenge tests only; clinical labels and reviewer study unavailable. | Independent blinded annotations and report of misses, omissions, false alarms. | Qualified reviewers / clinical owner |
| TD-03 | Speaker roles lack independent real-audio validation. | High | Role confirmation and synthetic checks exist; hardware and labels missing. | Per-turn/role held-out score and physical recording report. | Reviewers and audio device owner |
| TD-04 | Long-session browser behavior lacks hardware-backed 20–30 minute evidence. | Medium | Scripted/browser metrics do not establish real capture support. | Supported-browser run with interruptions, retries and preserved audio. | Device/operator availability |
| TD-05 | Deployment retention, security and institutional controls lack sign-off. | High | Engineering controls and buyer checklist exist; no deployment owner. | Exact-release security review, retention/deletion/restore checks, named approvals. | Institutional privacy/security/IT owners |
| TD-06 | FHIR output lacks receiver-specific profile and EHR integration evidence. | Medium | Serialization tests only; no receiving system sandbox. | Authorized profile validation and end-to-end sandbox transaction. | EHR integration owner |
| TD-07 | Model availability, licensing and artifact digests are incomplete for some candidates. | Medium | Reproducibility pack labels missing licenses/digests and unavailable models. | Local artifact manifest with digest/license evidence or candidate marked unavailable. | Model maintainer; source artifacts |
| TD-08 | Product value and economics are assumptions, not observed evidence. | Medium | Simulations and local-unit-economics assumptions are labeled. | Qualified user study and sourced operating costs; no fabricated adoption/ROI claim. | Product owner / study participants |

This is a planning index, not a replacement for the detailed [risk register](risk-register.md). External dependencies remain open until evidenced; assigning an owner role does not constitute approval.
