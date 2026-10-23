# Implementation status

Updated 24 October 2026. Blueprint version 2.2 remains the design source.
The first three sections below record historical milestones; the current state
and remaining release gates are described in Milestone 4.

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

## Milestone 3: local ASR adapter and immutable transcripts

Implemented operator-configured, artifact-hashed local model profiles, optional
faster-whisper 1.2.1 dependencies, separate durable transcription jobs,
authorization-aware heartbeat leases and exact immutable transcript publication.
The schema upgrade preserves original ingest job IDs and stages. Queue requests
are idempotent; retries for the same upload/profile snapshot reuse one ASR job.
The ingest worker cannot claim transcription work.

The adapter accepts original mono 16 kHz PCM arrays, forces English transcription,
consumes the full lazy result, preserves raw text/time values and publishes
estimated timestamps with unassigned speakers and explicit review flags.
Invalid/partial output never becomes a saved transcript. Canonical content hashes
and ETags bind each saved version; source input and model/runtime provenance are
retained. Transcript correction, approvals and export remain future work.

Real CPU inference with a pinned tiny English checkpoint passed a 7.26-second
synthetic speech smoke test, including a repeat with Python-level external
network calls guarded. See the [executed report](../evaluation/reports/local-asr-smoke-2026-10-23.md)
for observed text, configuration and limits. This tiny checkpoint is a smoke
fixture, not a selected clinical model. The [ASR runbook](runbooks/local-asr.md)
documents provisioning and cancellation/resource-isolation limitations.

Validation: the 51-test regression suite passed in both the pre-existing Python
environment and the fresh isolated `.[dev,asr]` environment. After the final
lease/migration/Unicode cases were added, all 18 transcription tests passed
(54 total tests now collected across the project). The isolated dependencies
passed `pip check`; evaluation JSON, Python compilation and whitespace checks
also passed. Unit tests require no model downloads; real inference is separately
recorded in the smoke report.

## Milestone 4: complete synthetic clinician workflow and operations

Milestone 4 implements the full synthetic clinician workflow: React/TypeScript
review UI, authenticated audio playback, manual/reference and corrected transcript
versions, typed evidence-linked facts, conservative reviewed-facts SOAP templates,
blocking findings, omission checks, documented clinical corrections, atomic
exact-version approvals, amendments and attributed Markdown/text/JSON exports.
The local launcher starts a separate worker process. Windows can generate its
own audible example; no patient or model assets are committed.

Validation includes regression tests, a real PostgreSQL encounter-to-approval
workflow in GitHub CI, and two local Chrome workflows: source review through
blocking medication clarification, approval and export; and compressed audio
upload through normalization and manual transcription. Mobile overflow checks,
the TypeScript production build and frontend dependency audit passed.

Backup/restore helpers preserve post-backup tombstones, verify backup checksums,
and report primary purging separately from backup expiry. Orphan reconciliation
defaults to dry run. Approved records and legal holds block generic deletion.
PostgreSQL support and its isolated CI service test passed for the preceding
release; subsequent migrations are covered by the same required CI job.

Implemented bounded separate-process media decoding, source/normalized checksums,
reconciliation, backup/restore and deletion operations, PostgreSQL migrations,
container configuration and a local evaluation harness. Late ASR publication is
fenced against a changed clinician transcript. The Windows launcher builds and
serves the interface and opens a browser; raw HTML files are not standalone apps.
See the [operations runbook](runbooks/operations.md).

The evaluation harness validates timestamps before scoring. A 23.06-second
synthetic medical probe was correctly rejected because the tiny model emitted a
segment beyond the recording duration. This is a failed sample, not evidence of
clinical suitability. See the [evaluation protocol](evaluation-protocol.md).

Remaining release gates require representative rights-cleared audio, independent
clinical adjudication, the large-v3 control and eligible challenger comparisons,
approved model licenses, production identity/security controls, deployment resource
isolation, retention/backup policies and clinical/governance approval. The model
registry still marks unexecuted comparisons as planned. Hosted processing and
real patient use are not enabled by completing the synthetic workflow.

Target hardware, clinical owner, retention policy and deployment approval remain
undecided. This milestone reports software tests only, with no clinical accuracy
or compliance claim. It does not complete the blueprint's Phase 1 exit gate.
