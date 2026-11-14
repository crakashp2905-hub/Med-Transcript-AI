# Migration and incident playbook

This playbook covers local synthetic development and rehearsals. It does not authorize deployment with patient data, replace an institution's incident process, or establish recovery targets for untested hardware.

## Local recovery objectives

- **RTO target:** restore a small synthetic SQLite snapshot and pass integrity validation within 60 seconds on the development workstation. Record the measured restore duration and the workstation/OS with each rehearsal. This is a local engineering threshold, not a service guarantee.
- **RPO target:** recover every acknowledged record present in the last completed, hash-verified backup. Writes after that snapshot are outside the recovery point and may be lost. The prototype has no scheduled backup cadence, so it does not claim a bounded wall-clock RPO for a running deployment.
- Rehearsals must include a successful synthetic restore and a rejected corrupted/incomplete backup. Record the snapshot manifest hash, recovered record counts, restore duration, and failure code. Hardware performance is not generalized beyond the machine measured.

## Roles and incident record

Assign an incident lead, an engineering operator, and a recorder before a rehearsal. One person may hold multiple roles in a local exercise, but the record must name each role. Use synthetic encounters only. Do not copy transcripts, audio, access keys, tokens, or raw provider errors into incident notes.

Record: incident ID, UTC start/end, affected build and commit, stage and stable error code, tenant-safe resource IDs, source and report hashes, observed impact, containment, recovery steps, validation evidence, unresolved risks, and the person who authorized each state transition. Preserve the original failed receipt and add a new superseding report; do not edit a prior benchmark or acceptance snapshot.

## Database migration rehearsal

1. **Stop and inventory.** Stop new synthetic jobs and wait for active workers to drain. Record the app commit, schema version, database location, storage location, free disk space, and integrity check result. Confirm no production mode or real-patient data is present.
2. **Back up.** Make a consistent database backup and a separate media/assets backup. Record their hashes and verify both can be read. A backup that was not restored in a rehearsal is unverified.
3. **Preflight.** Run `python -m services.offline_diagnostics`. Stop if the source is dirty, required local artifacts are absent, disk space is below the configured rehearsal reserve, or the diagnostic output is incomplete.
4. **Apply.** Run the migration using the versioned migration command for the selected app release. Capture the migration ID and result. Require transactional success or an explicit rollback record; never treat a partially applied migration as success.
5. **Validate.** Run schema and foreign-key checks, then the synthetic API and export journeys. Compare record counts, evidence hashes, approval bindings, and migration audit entries against the pre-migration receipt.
6. **Close or roll back.** Close only when all checks pass and the new build is bound to the validated schema. Otherwise stop writes, retain the failed database and logs, and follow rollback below.

## Rollback procedure

1. Stop API and worker processes so no further writes occur.
2. Preserve the failed database, asset tree, migration output, and process logs as a separate incident bundle. Hash them; do not overwrite the pre-migration backup.
3. Restore the verified pre-migration database and matching assets as a pair. Never restore only the database when media objects were created or rewritten by the failed migration.
4. Start the prior application commit in local-only mode. Run integrity checks and the same synthetic smoke journeys used before the migration.
5. Confirm source transcript hashes, note versions, approvals, audit entries, and export digests. Keep any post-backup writes blocked until a documented forward-recovery plan accounts for them.
6. Record whether rollback succeeded. If not, keep the service stopped and escalate to the system owner; do not manually edit approval or audit rows to force a green result.

## Synthetic incident scenarios

| Scenario | Containment and expected behavior | Recovery evidence |
| --- | --- | --- |
| ASR model directory is missing | Keep the recording and encounter in review-required state. Do not emit an empty successful transcript or approve a note. | Diagnostic output names the missing candidate path; retry succeeds only after the exact local asset is restored and hashed. |
| Upload response is lost after the server stored a chunk | Preserve the browser draft and retry with the same idempotency key. Do not create a duplicate audio asset. | Playwright retry journey shows one published upload and the same idempotency key on retry. |
| Disk becomes full during ingest | Stop writes, retain the incomplete source state, and return a stable storage error. Never publish an approved note from a partial recording. | Disk diagnostic, failed job receipt, and recovery result after space is restored. |
| Transcript changes after approval | Block stale exports and require a new reviewed version or amendment. | Old approval/export hashes remain immutable; new version has its own source and approval binding. |
| Migration fails after a partial step | Stop workers and writes; preserve the failed database; restore the verified matching database/media backup or keep the service stopped. | Migration log, backup hashes, restored integrity check, and synthetic smoke report. |

## Release stop criteria

Stop a release or pilot rehearsal if any of the following is true:

- source or benchmark evidence is stale, hash-invalid, or missing;
- a migration, database integrity check, backup verification, or restore rehearsal fails;
- partial or failed audio can appear as a complete transcript, note, approval, or export;
- a stale source can be approved or exported without an explicit new review;
- tenant-isolation, authorization, consent, retention, or audit-integrity checks fail;
- a required model, runtime, secret, TLS endpoint, or permission is missing or unverified;
- the unchanged 5% ASR gate fails, or the task requires independent clinical annotation that is not available;
- qualified clinical ownership, institutional sign-off, or the deployment country's requirements are unresolved.

An engineering smoke test can clear only its named software check. It cannot clear a clinical, security, privacy, backup, or institutional release gate.
