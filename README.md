# Med Transcript AI

English-only, clinician-reviewed outpatient documentation, based on the
[master blueprint](medical_transcription_agent_master_blueprint.md).

This is a **synthetic-data-only development API**: authenticated
encounters, clinician/tenant isolation, scoped authorization with expiry and
withdrawal, durable SQLite storage, and transactional metadata audit events.
It supports idempotent creation, bounded PCM WAV uploads, durable ingest/ASR
jobs, immutable timestamped transcripts, a clinician review interface, reviewed-fact
SOAP drafting, blocking verification, exact-version approval, amendments and
Markdown/text/JSON exports. A pinned
tiny English model passed a synthetic smoke test; clinical benchmarking is pending.

## Run locally

The quickest Windows start builds the interface and starts the API and its
separate worker. It also creates an audible synthetic consultation where a
Windows speech voice is available:

```powershell
./scripts/start.ps1
```

Open the loopback address printed by the launcher and enter its local access key.
Use **Open synthetic example** to explore the complete review workflow. Use
`-WithAsr` to install speech dependencies and configure a local model profile
as described below; `-WithPostgres` installs the PostgreSQL driver. Model weights
are never silently downloaded. The access key and development state live under
ignored `data/`; the key stays in browser memory and is not placed in URLs.

For an existing installed environment and built frontend:

```powershell
python -m services.launch --demo
```

The clinician workflow is source review → reviewed facts → saved SOAP draft →
verification → patient reconfirmation → exact approval → approved export.
Fixing a transcript invalidates dependent note approval; editing approved content
requires an amendment. Critical ambiguity cannot be dismissed with an ignore
button. Clinician additions have their own attribution and no invented citations.

Python 3.11+ is required. From this folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
$token = python -c "import secrets; print(secrets.token_urlsafe(32))"
$tenant = [guid]::NewGuid().ToString()
$clinician = [guid]::NewGuid().ToString()
$identities = @{}
$identities[$token] = @{tenant_id=$tenant; clinician_id=$clinician}
$env:MED_TRANSCRIPT_IDENTITIES = $identities | ConvertTo-Json -Compress
python -m uvicorn services.api.main:app_from_env --factory --host 127.0.0.1 --port 8000
```

Open [API documentation](http://127.0.0.1:8000/docs), select Authorize, and use
the generated token. Keep that token local. Use synthetic UUIDs for patients.
The database defaults to `data/development.sqlite3` (ignored by Git);
`MED_TRANSCRIPT_DB` overrides its path. Startup refuses missing/short tokens.

Example encounter request:

```json
{
  "patient_reference_id": "00000000-0000-4000-8000-000000000001",
  "patient_identifiers_confirmed": true,
  "synthetic_data": true
}
```

Send an `Idempotency-Key` header on encounter and upload-session creation.
Use an opaque UUID for each new operation and reuse it for retries. An identical
retry returns the original response for 24 hours; a changed payload with the
same key returns 409. Keys are scoped to the authenticated tenant, clinician,
and operation. Clients must retain the returned encounter ID beyond that window.

Creation does not authorize recording. Record scopes separately through
`POST /v1/encounters/{id}/authorizations`, with `scopes`, `policy_version`,
`method`, and a future timezone-aware `expires_at`. The permission endpoint
shows effective authorization; ASR remains disabled until local profiles are configured.
Withdrawal is repeatable and preserves its original timestamp.

## Upload and inspect synthetic audio

Only 16-bit PCM RIFF/WAV is currently supported: one or two channels,
8–48 kHz, at most 250 MB and 60 minutes. Other codecs require a future
sandboxed decoder. Use synthetic recordings only.

1. Create an encounter and record both `recording` and `local_processing` scopes.
2. `POST /v1/encounters/{id}/audio-uploads` with `Idempotency-Key` and JSON
   containing `bytes`, `sha256` (lowercase hex), and `media_type: "audio/wav"`.
3. `PUT` the raw file bytes to the returned `content_url`, with the same bearer
   authentication and `Content-Type: audio/wav`. This is not multipart upload.
4. `POST /v1/encounters/{id}/audio-uploads/{upload_id}/complete` to queue inspection.
   Repeating completion returns the same job, including after a lost response.
5. Run the separate local worker once for each queued job:

   ```powershell
   python -m services.api.ingest --db data/development.sqlite3
   ```

6. `GET /v1/jobs/{job_id}` to read the durable status and validated audio metadata.

The worker exits after one job, or reports `idle`; it does not automatically
transcribe the file. If `MED_TRANSCRIPT_ASSETS` overrides API storage, pass the
same directory using the worker's `--assets` option. By default, assets live in
the database's sibling `assets` directory. Only server-generated UUID filenames
are used. No unauthenticated media links or download routes are exposed.

Upload sessions expire after 15 minutes. Inspect a session with
`GET /v1/encounters/{id}/audio-uploads/{upload_id}`. Failed size/checksum checks
remove partial files and allow a whole-file retry within the session lifetime.
Chunk-resumable uploads are deferred. If the API process crashes mid-transfer,
create a new session; operator cleanup of abandoned files is described in the
[ingestion runbook](docs/runbooks/local-ingestion.md).

For an offline synthetic smoke demonstration (requires the `dev` dependencies):

```powershell
python -m services.demo_ingest
```

## Local speech transcription

Install optional ASR dependencies in the virtual environment:

```powershell
python -m pip install -e '.[dev,asr]'
```

The tested Windows/Python 3.13 dependency versions are captured in
`requirements/asr-windows-py313.lock.txt`. To reproduce that environment,
install it first, then install this project with `--no-deps -e '.[dev,asr]'`.
These pins are a development record, not a production security/release assessment.

Provision a converted faster-whisper model directory yourself from an approved
source and fixed 40-character commit revision. Keep it under ignored `data/models/`
or `models/`. Model downloading is separate from API/worker execution. After
reviewing its applicable terms, create a local artifact manifest:

```powershell
python -m services.asr.profiles --model-dir data/models/your-model --profile-id local-english-v1 --source owner/model --revision YOUR_40_CHARACTER_COMMIT --license-id YOUR_REVIEWED_LICENSE --out data/asr-profiles.json
$env:MED_TRANSCRIPT_ASR_PROFILES = (Resolve-Path data/asr-profiles.json).Path
```

The manifest command hashes the local files. It requires `model.bin`,
`config.json` and `tokenizer.json`; a supplied `preprocessor_config.json` is
hashed too. Without that file the pinned runtime's default feature extractor
is recorded in provenance. Do not delete the tokenizer: an incomplete local
model is rejected before loading. The tool does not verify license suitability,
clinical accuracy or that a claimed source revision produced those artifacts.

Restart the API with this environment variable. After successful audio ingestion,
request transcription with an `Idempotency-Key`:

```http
POST /v1/encounters/{id}/transcriptions
Content-Type: application/json

{"audio_asset_id":"UPLOAD_UUID","inference_profile_id":"local-english-v1"}
```

Run the separate ASR worker, then poll the returned job URL:

```powershell
python -m services.asr.worker --db data/development.sqlite3
```

Successful jobs link to `GET /v1/encounters/{id}/transcripts/{version_uuid}`.
Transcripts preserve original segment text, estimated timestamps, model/config
provenance, untranscribed intervals and an exact-version SHA-256/ETag. Speakers
remain unassigned, and language support and clinical completeness require review.
ASR currently accepts **mono, 16 kHz, 16-bit PCM WAV only**; resampling, stereo
attribution, diarization and general codec decoding are deferred.

For a local speech smoke run using your synthetic fixture and profile:

```powershell
python -m services.demo_ingest --synthetic-audio data/synthetic-fixture.wav --asr-profiles data/asr-profiles.json
```

The demo uses the first profile in that file. See the
[ASR runbook](docs/runbooks/local-asr.md) and
[executed synthetic smoke record](evaluation/reports/local-asr-smoke-2026-10-23.md).

## Verify

```powershell
python -m pytest -q
```

Tests cover access denial, cross-tenant and unassigned-clinician access,
authorization expiry/withdrawal, persistence across restart, transactional
audit records, concurrent retries, upload integrity, WAV structure/duration,
worker crash recovery, unsupported configuration, and redacted validation errors.

## Boundaries and next work

This development service uses operator-provisioned bearer credentials, not a
human SSO/session implementation. SQLite is a development storage choice;
SQLite schema upgrades are transactional and versioned, including upgrades from
the original foundation database. PostgreSQL, encryption, retention controls, immutable audit
storage and deployment hardening are required before a real-data pilot.
`synthetic_data: true` is an explicit developer attestation, not a detector of
patient information. Do not enter real patient information.

See [implementation status](docs/implementation-status.md) for the staged backlog.
Commit and push verified milestones to the configured GitHub remote; never
commit credentials, databases, recordings, or private annotations.
