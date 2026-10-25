# Requested work: delivery and dependencies

| Request | Delivered | Remaining dependency / limit |
|---|---|---|
| P0 CI | Investigated exact account billing failure; constrained Python installs, patched pip advisories, added dependency automation/audit and separate manual model lane | New main run 40206920869 passed all five jobs, including PostgreSQL and container; prior billing restriction did not recur |
| P0 full consultations | Three pinned, checksum-recorded English mock consultations, 31m39.6s, 384 reference turns, reproducible full audio | Independent clinician adjudication and acceptance cohort |
| P0 clinical metrics | Normalized/raw WER, CER, independent concept precision/recall, omissions/insertions and per-category metrics; failed cases included | Real independently annotated clinical gold |
| P1 best eligible ASR | Existing ranking/gate retained: no candidate passes strict 5%; no unsupported model promotion | A passing candidate plus verified timestamp output is required before app integration |
| P1 drafting adapters | Deterministic, configurable loopback and hosted JSON adapters; bounded requests, reviewed citations, disclosure gates, immutable unapprovable proposals | Provision approved local model for quality testing; hosted accounts/paid permission remain disabled |
| P1 typed facts | Evidence character spans, subject/assertion/time/category and optional medication/dose/allergy/site fields; conservative extraction returns unreviewed facts | Clinical calibration and complex assertion resolution |
| P1 verification | Independent critical-field/unsupported-term rules; synthetic adversarial regression report | Independent clinician challenge set and semantic validation; rules are not a validated entailment model |
| P1 diarization | Optional hash-checked offline adapter, anonymous clusters, explicit clinician role confirmation | Owner-approved model license/access/runtime, actual accuracy evaluation and worker integration |
| P1 note/time/latency/cost | Annotated note scoring, immutable scoped review sessions, edit counts, wall time, p50/p95 aggregation, unknown cost handling | Real clinician study and verified pricing/hardware accounting |
| P2 pilot | Threat model, security/retention control requirements and supervised pilot protocol | Institution, legal, identity/infrastructure and clinical approvals |

The best screened ASR remains Omi Q8 at **197/2264 = 8.70% normalized WER**, above the strict 5% ceiling. All seven completed local candidates fail; hosted/gated/resource-blocked candidates remain visible and unranked. The application stays on its existing development inference path; this delivery does not establish a clinically eligible ASR, an approved pilot or production security.

See `runbooks/ci.md`, `clinical-annotation.md`, `runbooks/drafting-and-diarization.md`, `pilot-security-requirements.md`, the full-consultation dataset README, and `evaluation/reports/clinical-adversarial-2026-10-25.json`. The attached development checklist was treated as planning context; this report maps the ten explicitly requested items and distinguishes engineering preparation from dependencies requiring human action.

Validation: 126 local tests passed, one PostgreSQL test skipped locally; the hosted PostgreSQL job passed. Frontend build and production audit passed. The local Python advisory audit reported no known dependency vulnerabilities after the pip update (editable application advisory lookup skipped). All 16 synthetic adversarial labels matched: 9 unsafe detections, 7 unchanged controls, no fixture false positives/negatives. These are regression results, not clinical acceptance. [Green CI run](https://github.com/crakashp2905-hub/Med-Transcript-AI/actions/runs/40206920869).
