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

## Next milestones

1. Add idempotent creation, PostgreSQL migrations and durable job state.
2. Add bounded upload sessions, checksum validation and sandboxed media decoding.
3. Implement local faster-whisper adapter with pinned local artifacts, original
   timeline mapping and honest coverage/uncertainty metadata.
4. Add React/TypeScript review UI with audio playback and immutable transcript edits.
5. Add typed facts and constrained SOAP drafting with validated evidence references.
6. Add blocking findings, exact-version approval, amendments and approved exports.
7. Run the model registry's staged evaluation and clinical/governance release gates.

Target hardware, clinical owner, retention policy and deployment approval remain
undecided. This milestone reports software tests only, with no clinical accuracy
or compliance claim. It does not complete the blueprint's Phase 1 exit gate.
