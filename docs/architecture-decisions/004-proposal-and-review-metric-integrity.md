# ADR 004: proposal and review-metric persistence integrity

Status: implemented; verification receipts determine release readiness.

Proposals and review-session bodies were immutable by ordinary SQL updates, but their read paths did not consistently recompute stored hashes. Review-completion records had no separate integrity seal. A corrupted source pointer or timing record could therefore be displayed before an integrity check.

Validate draft, extraction, semantic-check and review-session records through bounded typed contracts without rewriting legacy serialization. Require exact proposal IDs, source hashes, encounter-scoped source/note references and semantic claim coverage. Proposed facts remain unreviewed. Unknown/duplicate claims and missing or malformed provider fields are rejected before publication. Sanitize schema errors so Pydantic input values do not escape into logs or API responses.

Verify review-session hashes when listing, completing or retrying a review. Store a review-completion hash in a separate session-bound integrity table in the same transaction as the completion. Check the seal on reads and idempotent retries; an existing seal with a missing metric is a failure rather than an uncompleted session. Session deletion during authorized purge cascades to its seal.

An additive migration seals existing metric bodies once, labels them `legacy_snapshot_not_external_attestation`, and preserves their original bytes. Earlier records without structured edit counters remain unknown for those counters; validation does not inject invented zero measurements. Existing bodies and immutable approvals are not edited.

The API route/request schema remains unchanged. Missing, changed or wrongly scoped persisted artifacts return a non-sensitive integrity code. This is local tamper detection: a database owner capable of coherently rewriting all bodies, hashes and seals is outside the guarantee. Self-reported active time remains unverified; browser wall time and programmatic review are not clinician observations.

Operational job receipts and configuration dictionaries still have separate contracts. This change does not claim that every persistence boundary in the application has completed the broader typed-contract checklist.
