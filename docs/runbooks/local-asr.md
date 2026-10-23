# Local ASR development worker

This worker is enabled by an operator-provisioned profile; the HTTP client can
select a configured profile ID, never a model path or remote provider. The API
stores its immutable configuration snapshot in SQLite. A job refers to that
snapshot hash and a successfully ingested upload. Changed model/configuration
snapshots are separate inputs; identical upload/profile pairs reuse one job.

## Provisioning and execution

Install `.[dev,asr]` in a virtual environment. Use a converted local model with
a tokenizer, model/config files and any associated vocabulary/preprocessor
files. Create a manifest with `python -m services.asr.profiles` and configure
`MED_TRANSCRIPT_ASR_PROFILES` before API startup. The manifest command never
downloads models, accepts gated terms, or marks a model clinically validated.
Review source identity, applicable terms and artifact provenance separately.

The worker checks every manifested file's SHA-256 and requires the root file
set to match. Symlinked model files and unexpected root files are rejected.
Copy provisioned artifacts to a dedicated regular-file directory if needed;
do not point directly at a shared cache of symlinks. Missing tokenizer files
fail closed, preventing the upstream tokenizer-download fallback. Missing
preprocessor configuration uses the pinned runtime's defaults and is disclosed
in transcript provenance. Runtime packages and the artifact/profile hashes
are recorded with the output.

Only original mono 16 kHz PCM samples are accepted. The adapter converts signed
16-bit samples to float32 without changing the timeline, and passes the array
directly to the engine, avoiding general media decoding. It forces English
transcription, disables VAD and word timestamps, and consumes the entire lazy
segment iterator before publication. Exactly zero PCM samples produce an empty
digital-silence result without executing model inference; this is not a general
speech/noise or language detector.

Run `python -m services.asr.worker --db PATH` once per queued job. The worker
uses the database's sibling `assets` directory unless `--assets` is supplied.
Use the same asset root as the API. A successful ingest job alone never triggers
ASR. The API's `inference_enabled` health field indicates configured ASR profiles,
not that a worker is running or that its hardware/dependencies are ready.

## Authorization, leases and output

Every claim and publication checks active recording/local-processing grants.
Progress checkpoints and a heartbeat renew a five-minute lease. A later worker
can recover abandoned leases, up to three attempts. Lease tokens fence late
results; one running ASR job is allowed per development database. Withdrawal
cancels queued/running jobs and prevents transcript publication.

Native inference cannot be forcibly interrupted in the middle of a decoder
call by this Python worker. Cancellation takes effect at the next checkpoint;
process supervision, hard timeouts and resource isolation remain required
hardening work. Separate databases do not coordinate a shared GPU. Do not
assume this lease mechanism enforces device-wide capacity or immediate cessation
of native computation after revocation.

Invalid output, nonfinite/out-of-range timestamps, excessive output, bad Unicode,
source corruption and partial-generator failures cannot create a transcript.
Public errors use safe codes; provider exception bodies are omitted. Transcript
publication, job success and audit metadata commit together. Raw transcript
versions reject database updates; corrections will require new versions.

Segment text and raw model time values are preserved. Millisecond timestamps
are estimates, with overlapping estimates flagged. Untranscribed intervals
include possible silence, missed speech and other unknown causes; they are
not proof that audio is missing. Forced English does not prove English input.
All outputs remain `review_required`, with unknown speaker roles, uncertain
language status and unverified clinical coverage. There is no approval path yet.

SHA-256 uses UTF-8 JSON with sorted keys, compact separators, Unicode retained
and nonfinite numbers forbidden. It covers the stored transcript body; the
response's added `sha256` field and HTTP headers are excluded. Generated version
and segment IDs mean separate runs need not have identical hashes. Hashes bind
exact saved content, not its clinical correctness.

The current app remains synthetic-only. Python socket guards used in the smoke
test are not an operating-system egress policy. Validate host/container network
controls, retention, access, audit integrity and model performance before a pilot.

Implementation references: [faster-whisper v1.2.1 source](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)
and [upstream usage documentation](https://github.com/SYSTRAN/faster-whisper).
