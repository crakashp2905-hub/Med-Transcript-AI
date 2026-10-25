# Security, retention and supervised pilot requirements

Prepared requirements, not approval to process patient data. Current operation remains synthetic/public mock recordings and clinician-reviewed prototypes. A named clinical owner, security owner, deployment region, legal/privacy review and institution-approved consent/retention policy are required before a real-data pilot. Do not invent retention periods or jurisdictional compliance claims.

Threat model: sensitive audio/text can leak through credentials, uploads, worker temporary files, model prompts, exports, backups, logs and support artifacts. Cross-clinician access, replay/stale approvals, malicious transcripts/prompt injection, model hallucinations, incorrect speaker attribution and abandoned processing after consent revocation can affect clinical safety. Existing scoped authorization, immutable versions, explicit review and revocation checks address parts of this model; they do not establish production compliance.

Required deployment evidence:

| Area | Required control and evidence | Dependency |
|---|---|---|
| Identity | Institutional SSO/MFA, least privilege, role lifecycle, short-lived credentials and access review | Identity provider / owner |
| Storage | TLS, encrypted disks/database/backups, managed key access/rotation, isolated environments, restore exercise | Infrastructure owner |
| Retention | Approved durations for audio, normalized copies, transcripts, notes, exports, logs and backups; legal holds and deletion exceptions | Clinical/legal owner |
| Deletion | Exercise existing purge/reconciliation against all artifacts and new proposal/review tables; account for offline exports, backups and provider copies | Operations + policy |
| Audit | Controlled audit access, external tamper-evident sink, synchronized clocks, incident review and export traceability | Infrastructure/security |
| Inference | Approved model licenses, pinned hashes, no unapproved remote downloads, isolated network egress, hosted processor contract/region and spending cap | Model/privacy owner |
| Safety | Audio completeness, diarization confirmation, evidence review, critical-field checks, verified clinician sign-off, rollback and incident escalation | Clinical owner |

A supervised pilot protocol must specify inclusion/exclusion criteria, English-language eligibility, recording consent, manual fallback, clinical escalation, clinician training and stop criteria. Choose a sample size and independently adjudicated acceptance cohort before observing results. The existing 5% normalized WER requirement is necessary but insufficient: define clinical error tolerances, note factuality/omission thresholds, speaker-role accuracy, latency limits and correction-time targets with clinicians. No model currently meets even the lexical gate.

Collect paired baseline/manual and assisted note tasks with randomized order, comparable cases, reviewer consent and an independent correctness assessment. Measure fact precision/recall by category, critical errors, completeness, wall/active correction time, edit counts, end-to-end p50/p95 latency, failure rate and total cost per successful consultation. Separate self-reported active time from observed time and local hardware cost from provider charges. Never report test-fixture timing as clinician productivity. Define review cadence, pause thresholds and incident ownership before recruitment.

New review-session endpoints store server-observed wall duration and token edit counts without note text in telemetry. Active time is explicitly self-reported/unverified. Immutable records remain scoped to the encounter and included in purge. A real clinician study, externally managed encryption/audit, backup retention enforcement and legal approval remain unperformed dependencies.
