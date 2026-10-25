# Med Transcript AI

English-only, clinician-reviewed outpatient documentation, based on the
[master blueprint](medical_transcription_agent_master_blueprint.md).

This is a **synthetic-data-only development API**: authenticated
encounters, clinician/tenant isolation, scoped authorization with expiry and
withdrawal, durable SQLite storage, and transactional metadata audit events.
It supports idempotent creation, bounded audio uploads, durable ingest/ASR
jobs, immutable timestamped transcripts, a clinician review interface, reviewed-fact
SOAP drafting, blocking verification, exact-version approval, amendments and
Markdown/text/JSON exports. A pinned
tiny English model passed a synthetic smoke test; expanded public mock benchmarks are complete and independent clinical acceptance remains pending.

The [2026-10-25 delivery status](docs/delivery-status-2026-10-25.md) covers full-length consultation cases, clinical metrics, drafting adapters, evidence-linked facts, independent verification rules, review telemetry and pilot requirements, with explicit account/model/clinical dependencies. These additions remain development features; no candidate has met the 5% ASR gate.

The [local dependency follow-up](docs/local-dependencies-2026-10-25.md) records real Qwen drafting tests, provisioned public diarization models, worker/UI integration and measured limitations. Start local model proposals with `scripts/start.ps1 -WithAsr -LocalDrafting -Port 8002`; experimental speaker clustering is separately opt-in with `-PublicDiarization`.

The [completion review](docs/completion-2026-10-25.md) adds stronger omission/structured-field checks, atomic evidence spans, timed review, version comparison and optional independent local model verification. The [eight-model ranking extension](evaluation/expanded-extension-leaderboard-v2.html) includes Qwen3 ASR at 13.74%; none meets 5%.

## Measured ASR ranking

The [expanded ranking and playable recordings](evaluation/expanded-leaderboard.html) now includes **all seven local configurations on 118 clips from 20 consultations, 2,264 reference words**. **Omi GGUF Q8 leads at 8.70% normalized WER; none meets the required ≤5%.** All final runs processed all clips successfully. [Grouped results](evaluation/reports/expanded-comparison-2026-10-24.md) include recording-day, consultation and speaker-role breakdowns. Seven gated, resource-blocked or user-disabled hosted configurations remain visible and unranked.

Generate publications from complete local runs with `python -m services.publish_expanded`. Rebuild scores from the committed corpus and reports, without model downloads or paid calls:

```powershell
python -m services.benchmark_ranking --manifest evaluation/datasets/primock57-expanded-v1/manifest.json --lock evaluation/datasets/primock57-expanded-v1/lock.json --ledger evaluation/expanded-ledger.json --out evaluation/expanded-leaderboard.json
python -m services.expanded_summary
```

Paid medical services may improve accuracy, but have not been measured on this corpus. See the [hosted-model evidence and comparison constraints](evaluation/reports/hosted-model-evidence-2026-10-24.md). The application dictation model remains unchanged; these text-only benchmarks do not establish clinical admission.

The user revised the maximum normalized WER to **5%**. The expanded comparison uses **118 frozen clips from 20 new consultations across all five recording days: 2,264 reference words and 13m 50s of audio**, with all seven local configurations evaluated as text-only recognizers. The initial target was 120 clips; one sparse role supplied one eligible utterance instead of three. Historical datasets and results remain unchanged.

During execution, [local progress](http://127.0.0.1:8766/expanded-progress.html) refreshes automatically. To serve it after restarting: run `python -m services.benchmark_progress --watch` and, in another terminal, `python -m http.server 8766 --bind 127.0.0.1 --directory evaluation`. The public evaluation directory is served locally; the private application data directory is excluded. Scores appear only for complete integrity-checked runs.

The earlier [follow-up validation](evaluation/reports/follow-up-validation-2026-10-24.md)
tested the two screening leaders on 30 fixed clips from five additional
consultations (575 reference words). **Omi GGUF Q8: 8.70%; Parakeet ONNX
INT8: 13.91% normalized WER. Neither meets the historical 3% or current 5% requirement.** Omi leads this
follow-up; these development results do not establish clinical acceptance.
Open the [follow-up comparison with playable audio](evaluation/validation-leaderboard.html).
The dataset, references, pinned model configurations and full hypotheses are
committed separately from the original screening set. Reproduce with:

```powershell
.\.venv\Scripts\python.exe -m services.benchmark_ranking --manifest evaluation/datasets/primock57-validation-v1/manifest.json --lock evaluation/datasets/primock57-validation-v1/lock.json --ledger evaluation/validation-ledger.json --out evaluation/validation-leaderboard.json
.\.venv\Scripts\python.exe -m services.validation_summary
```

Open [the standalone comparison page](evaluation/leaderboard.html) in a browser,
or read [the ranked results](evaluation/leaderboard.md). The page opens directly
without an API server and includes playable reference recordings. All 13 blueprint
candidates have an explicit ledger entry; seven configurations including the
additional tiny.en fixture have measured results. Gated, resource-limited and
user-disabled hosted candidates remain unranked. No paid calls were made.

The [frozen dataset](evaluation/datasets/primock57-smoke-v1/README.md) includes
six CC-BY-4.0 mock-consultation recordings, manual reference text, checksums and
the source revision. It is the source of truth for this **screening** ranking,
not a clinical acceptance corpus. The current normalized WER limit is ≤5% (historical reports used ≤3%); none
of the tested configurations currently passes. Rebuild the leaderboard with:

```powershell
.\.venv\Scripts\python.exe -m services.benchmark_ranking
```

## Run locally

The quickest Windows start builds the interface and starts the API and its
separate worker. It also creates an audible synthetic consultation where a
Windows speech voice is available:

```powershell
./scripts/start.ps1
```

You can also double-click `Open Med Transcript.cmd`. The launcher opens your
browser when the server is ready. Keep its console window open while using the app.
Open the loopback address printed by the launcher and enter its local access key.
Do not open `index.html` directly: the interface requires the running API and built
assets. If port 8000 is occupied, use `./scripts/start.ps1 -Port 8001`.
Use **Open synthetic example** to explore the complete review workflow. Use
`-WithAsr` to install speech dependencies and configure a local model profile
as described below; `-WithPostgres` installs the PostgreSQL driver. Model weights
are never silently downloaded. The access key and development state live under
ignored `data/`; the key stays in browser memory and is not placed in URLs.

For an existing installed environment and built frontend:

```powershell
.\.venv\Scripts\python.exe -m services.launch --demo --open
```

The clinician workflow is source review → reviewed facts → saved SOAP draft →
verification → patient reconfirmation → exact approval → approved export.
Fixing a transcript invalidates dependent note approval; editing approved content
requires an amendment. Critical ambiguity cannot be dismissed with an ignore
button. Clinician additions have their own attribution and no invented citations.

### Microphone dictation

Create an encounter, confirm the synthetic-speech/recording authorization in
**Microphone dictation**, then choose **Start dictation**. Allow the browser's
microphone prompt, speak English and choose **Stop & transcribe**. The application
uploads the recording, waits for local inspection, queues the configured ASR
profile and displays the unreviewed transcript automatically. Audio never goes
to a browser speech-recognition service or hosted ASR provider.

This is stop-to-transcript dictation, not word-by-word streaming. Processing time
depends on the configured model and local hardware. Recordings are limited to
five minutes or 25 MB. Discard stops capture without uploading; failed uploads
can be retried from the retained local recording. You can also save that recording
locally. Browser microphone access requires localhost or HTTPS; Chrome and Edge
are the tested Windows browsers. An ASR profile and the local worker are required.

The launcher reads `MED_TRANSCRIPT_ASR_PROFILES`, or an explicitly configured
`asr_profiles_path` in ignored `data/local-config.json`. It does not download or
switch models automatically. This workstation retains its existing tiny.en
development profile for dictation. All tested models still fail the 5% quality
requirement, so use synthetic test speech only and review every result.

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

The API schema is available at `/openapi.json`; the clinician interface is at `/`
after building the frontend. Keep the token local. Use synthetic UUIDs for patients.
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

WAV, MP3, M4A/MP4, WebM and Ogg audio uploads are supported: one or two channels,
8–48 kHz, at most 250 MB and 60 minutes. Install the `media` extra for decoding.
The worker normalizes supported recordings to mono 16 kHz PCM in a bounded
separate process and preserves the original checksum. Windows process isolation
does not provide a kernel-enforced decoder memory sandbox. Use synthetic recordings only.
See the [operations runbook](docs/runbooks/operations.md) for deployment,
backup, restore, deletion and reconciliation, and the
[evaluation protocol](docs/evaluation-protocol.md) for measured model limitations.

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

The [independent validation workflow](docs/independent-validation-workflow.md)
provides hash-bound source-only annotation packets, two-reviewer disagreement
comparison, third-reviewer adjudication intake, failure-inclusive paired-study
analysis and a reproducible [release evidence inventory](evaluation/reports/release-readiness-2026-10-25.json).
These tools do not supply clinician observations or authorize real-patient use.

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
