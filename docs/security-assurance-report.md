# Security assurance report — 2026-11-14

**Assessment source commit:** `0639044ee4f68af4f159bc03b5a73a9e2d8dc6e7`  
**Disposition:** **DEVELOPMENT ONLY. Clinical release is unauthorized.**

## Scope

This is a source- and test-based assessment of the local synthetic/public-mock prototype. It is not an external audit, penetration test, legal or privacy approval, production deployment review, or evidence that real patient data may be processed. The requested 5% normalized WER gate remains unmet; clinical accuracy and independent clinical acceptance are not established.

## Controls and evidence

| Area | Current evidence | Limits |
|---|---|---|
| API authorization and JSON request boundaries | Local authentication, role, cross-scope, strict JSON, size and replay tests; [MTA-13-05](../evaluation/reports/master-task-mta-13-05-8dcc73d.json), [MTA-13-06](../evaluation/reports/master-task-mta-13-06-05e1262.json). | No independent penetration test or production identity-provider validation. |
| Investor viewer | Viewer response minimizes identifiers and model configuration; reads of non-synthetic legacy encounter and deletion records are hidden; [MTA-13-20](../evaluation/reports/master-task-mta-13-20-88fdbb5.json). | No real-patient corpus or production Workspace identity configuration was used. |
| Audio storage and paths | Asset-root and path checks plus upload tests; [MTA-13-07](../evaluation/reports/master-task-mta-13-07-0c6998d.json), [MTA-13-08](../evaluation/reports/master-task-mta-13-08-5169656.json). | POSIX mode checks and directory symlink checks were skipped on Windows. Windows ACLs and race-free local filesystem operations are not established. |
| Worker consent revocation | Queue-time and in-flight worker cancellation tests; [MTA-13-09](../evaluation/reports/master-task-mta-13-09-637348a.json). | Authenticated consent route coverage remains unverified. |
| Tamper detection | Local audit chain, approval seal, source/proposal links and export digest tests; [MTA-13-17](../evaluation/reports/master-task-mta-13-17-fb8047d.json). | No external immutable audit sink or privileged-database-operator protection; focused PostgreSQL parity was not tested. |
| Egress denial | A no-pull Docker runner uses `--network none`; [MTA-13-18](../evaluation/reports/master-task-mta-13-18-79c97d3.json). | Docker is absent here, so isolation was not executed. Host firewall policy is documented but not applied or verified. |
| OS/database privilege separation | Container runs non-root with read-only roots and dropped capabilities in the static container contract. | Separate migration and application database roles remain unimplemented. |
| Encryption, retention and deletion | Requirements and local backup/deletion tests are documented. | Institution-managed keys, approved retention, deletion of all external copies, and an available pinned encryption implementation remain unresolved. |

## Current check failures and blockers

- The repository-wide Python format check fails on four concurrent ASR benchmark files; they were not modified during this assessment.
- The master ledger audit test fails at MTA-01-02 because a task marked verified has no required runtime receipt.
- No Docker executable is installed, so the egress-denied container runner could not be executed.
- Qualified independent clinical reviewers, a named clinical/privacy owner, deployment jurisdiction, production identity registration, managed key custody, and operator firewall evidence are unavailable.

## Required before any real-data pilot

Complete least-privilege database role separation; provision and verify filesystem ACLs, encryption, retention and deletion; run the egress-denied test image on an isolated runner; restore CI and ledger integrity; obtain institution-approved identity, consent, security, privacy and clinical sign-off; and complete independent clinical annotation and acceptance. Preserve all failed benchmark cases and do not represent synthetic or model-generated results as clinical validation.

## Machine-readable evidence

The artifact [`security-assurance-2026-11-14.json`](../evaluation/reports/security-assurance-2026-11-14.json) binds the source commit, source-file digests, evidence report digests, known check failures and external dependencies.
