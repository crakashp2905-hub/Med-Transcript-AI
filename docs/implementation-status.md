# Implementation status

Updated 23 October 2026. Blueprint version 2.2 remains the design source.

## Milestone 1: synthetic encounter foundation

Implemented FastAPI application factory, strict request schemas, server-derived
identity scope, encounter ownership, explicit patient-confirmation attestation,
English/local-only configuration, scoped authorization creation/expiry/withdrawal,
durable SQLite transactions and content-free action metadata. Reads and writes
enforce both tenant and assigned clinician. Validation errors omit submitted
values. Responses include request IDs and no-store headers.

Authorization scopes are combined across active unexpired grants. Withdrawal
revokes the specified grant; any independently active grants remain effective.
No background jobs, audio capture or external requests exist in this milestone.
Future workers must recheck policy inside their processing/dispatch transaction;
the permission endpoint is informational, not a reusable authorization token.

Validation: 15 automated tests passed on Python 3.13.5. OpenAPI generation
also passed. The local environment emits a third-party Starlette/AnyIO
deprecation warning. Tests needed execution outside the Windows sandbox because
its test-client worker threads stalled; no live services or patient data were used.

## Milestone 2: idempotency and synthetic PCM WAV ingestion

Implemented required, actor/tenant/operation-scoped idempotency keys for encounter
and upload creation, 24-hour replay records, conflict detection and serialized
transactions. Existing foundation SQLite databases upgrade in place using
transactional, versioned migrations. PostgreSQL is still deferred.

Authenticated upload sessions accept bounded raw WAV transfers with declared
byte count and SHA-256, cleanup on known failure, original hashes and short
expiry. Completion atomically creates one persistent ingest job. The separate
local worker inspects 16-bit PCM WAV only, enforces format/duration bounds,
records original audio metadata and uses bounded crash-recovery leases. It
rechecks effective authorization before dispatch and publication. Withdrawal
cancels queued/running jobs without discarding completed history. No speech
recognition or note drafting is enabled by the ingest-success state.

See the [runbook](runbooks/local-ingestion.md) for interruption, retry and cleanup
limitations. General media decoding, resumable chunks, automated orphan cleanup,
encryption and production job supervision remain unfinished.

Validation: all 36 automated tests passed on Python 3.13.5, including concurrent
encounter retry and upload completion, legacy migration, checksum/size errors,
malformed/unsupported WAVs, duration bounds, authorization withdrawal during
inspection, asset tampering, expired authorization and crashed-worker recovery.
The final concurrency/inspection adjustments also passed their targeted checks.
The offline synthetic demo completed successfully with a 1,000 ms, 16 kHz mono
PCM result and the original checksum. The third-party deprecation warning from
Milestone 1 remains; no external service or ASR model was called.

## Next milestones

1. Add sandboxed codec decoding and upload storage/recovery hardening.
2. Add PostgreSQL deployment and migration validation.
3. Implement local faster-whisper adapter with pinned local artifacts, original
   timeline mapping and honest coverage/uncertainty metadata.
4. Add React/TypeScript review UI with audio playback and immutable transcript edits.
5. Add typed facts and constrained SOAP drafting with validated evidence references.
6. Add blocking findings, exact-version approval, amendments and approved exports.
7. Run the model registry's staged evaluation and clinical/governance release gates.

Target hardware, clinical owner, retention policy and deployment approval remain
undecided. This milestone reports software tests only, with no clinical accuracy
or compliance claim. It does not complete the blueprint's Phase 1 exit gate.
