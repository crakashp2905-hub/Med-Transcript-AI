# Local synthetic ingestion

The API stores raw upload bytes; a separate trusted local process validates
PCM WAV structure and metadata. General codec decoding and clinical processing
are not enabled. The WAV inspector uses bounded header reads, chunk-count and
file-size limits, and seek-based inspection. It never executes media content.
This is not the blueprint's future sandboxed codec-decoding service.

## Storage and authorization

Keep the SQLite file and its sibling `assets` directory together. If using an
explicit asset directory, configure the API and worker consistently. File paths
are built from generated upload UUIDs; clients cannot choose paths or remote URLs.
The original size and SHA-256 are checked at transfer, completion, and worker
execution. Job payloads contain identifiers, not clinical text.

Both recording and local-processing authorization must be active at session
creation, transfer, completion, claim and result publication. Withdrawal cancels
pending/running jobs if no other active grant permits processing. Expiry is also
checked at dispatch and publication. A late result cannot overwrite a cancelled
job. Succeeded historical jobs remain visible to the assigned clinician; withdrawal
is not a deletion request and does not erase stored audio.

## Retry and interruption behavior

- Encounter and upload-session creation require an opaque idempotency key. Retry
  with the same key/payload for 24 hours. Responses and resource changes commit
  together. Keys are stored as digests; response records include synthetic IDs.
- Completion is naturally idempotent by upload ID. It creates one job in the
  same database transaction that marks the session complete.
- Known transfer failures remove partial files and reset the session for a
  whole-file retry. An uploaded session can proceed to completion after a lost
  successful transfer response; inspect its status first.
- An API process crash can leave an `uploading` session or an orphaned file.
  Create a new session. Do not mark an incomplete session complete manually.
- The worker claims one job with a five-minute lease. A later invocation recovers
  an expired lease. At most three worker attempts are permitted; exhausted jobs
  fail with `worker_retry_exhausted`. Leases prevent an abandoned worker from
  publishing after another worker has claimed its job.
- Invalid/unsupported WAV files and integrity failures are terminal. Correct
  the source and create a new upload instead of retrying unchanged invalid bytes.

## Abandoned-file cleanup and recovery

Stop the API and workers before manual cleanup. Back up permitted development
state first. Inspect uploads by UUID and status in SQLite. Only remove `.part`
files and raw assets belonging to expired, incomplete sessions after confirming
no process is writing them. Completed assets must remain available for queued
jobs. Never delete the SQLite file as an upload-retry mechanism.

Filesystem rename and the database commit are not a single atomic transaction.
A crash between them can leave an orphan asset; it cannot create a succeeded
job without validation. Automated orphan reconciliation, disk quotas, concurrent
upload limits, retention/deletion, encrypted storage, and PostgreSQL deployment
remain required hardening work. Bind development services to loopback and use
only generated synthetic data.
