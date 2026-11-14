# Product backlog v1

**Status:** internal engineering plan; priorities are provisional and are not customer research.
**Scope:** English, local-first, clinician-supervised documentation prototype.

| Rank | Item | Priority | Current evidence / gap | Acceptance evidence | Dependency / owner |
|---:|---|---|---|---|---|
| 1 | Improve full-conversation ASR and clinical-term accuracy | P0 | Current eligible candidates do not meet the unchanged 5% normalized-WER gate; frozen failures remain visible. | Fresh exact-source report improves development audio coverage and errors without invalid timestamps; retain all prior failures and gate. | Existing local audio/models; engineering |
| 2 | Reduce speaker-turn and role errors | P0 | Role labels need independent scoring; physical device not identified. | Per-turn and per-role report on held-out labeled audio, plus safe unknown/human-review fallback. | Independent annotators and named audio hardware; engineering + clinical owner |
| 3 | Validate medication, negation, allergy and omission checks | P0 | Synthetic challenge coverage exists; independent sensitivity and false-alarm rates are unknown. | Blinded, adjudicated cohort; report critical misses, omissions and false alarms; model verdict cannot clear approval. | Qualified reviewers and acceptance cohort; clinical owner |
| 4 | Complete interruption, retry, edit and stale-approval workflows | P0 | Existing focused checks do not constitute a complete long-session race matrix. | End-to-end exact-commit cases preserve source, invalidate dependent proposals, and reject stale approvals. | Browser/runtime execution; engineering |
| 5 | Exercise long sessions and physical multi-channel capture | P1 | Synthetic long-workflow and channel logic do not establish physical hardware support. | Documented 20–30 minute runs on named device/OS/interfaces, including interruption and channel-count matrix. | User supplies device; engineering + device operator |
| 6 | Complete independent clinical annotation and acceptance cohort | P1 | Reviewer packets/schema can be prepared; qualified reviewers are not available. | Source-audited annotations, reviewer qualifications, adjudication record, distinct acceptance split. | Two qualified reviewers and clinical owner |
| 7 | Close deployment security and retention review | P1 | Local controls and checklists exist; no institution/deployment owner has signed off. | Threat review, retention/deletion/restore evidence, access review and owner approvals at exact release. | Institution security/privacy/IT owners |
| 8 | Validate approved-note handoff against a receiving EHR profile | P2 | Prototype serialization is tested; receiver profile and certification are absent. | Receiver-specific validation and authorized sandbox end-to-end transaction; no certification claim absent formal approval. | EHR integration owner and sandbox |
| 9 | Measure clinician correction time and workflow fit | P2 | Scripted simulations are engineering evidence only. | Preregistered task protocol, qualified participants, blinded case set, timing and correction analysis. | Qualified reviewers and approved study protocol |

## Intake and completion rules

- Keep each work item tied to a reproducible artifact, exact source revision and explicit acceptance condition.
- Do not close an evidence-dependent item using synthetic tests, model self-evaluation, or an unavailable reviewer.
- Preserve benchmark failures and prior reports; publish new runs as new versions.
- Re-rank only when new source-audited evidence or an accountable owner changes a dependency. No market demand or customer value is inferred here.

Related planning: [prioritization rubric](prioritization-rubric-v1.md), [roadmap](roadmap-v1.md), [technical debt](technical-debt-v1.md), [risk register](risk-register.md), and [release note](release-notes-v0.4.1.md).
