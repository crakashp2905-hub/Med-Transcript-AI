# Med Transcript AI

English-only, clinician-reviewed outpatient documentation, based on the
[master blueprint](medical_transcription_agent_master_blueprint.md).

The first milestone is a **synthetic-data-only API foundation**: authenticated
encounters, clinician/tenant isolation, scoped authorization with expiry and
withdrawal, durable SQLite storage, and transactional metadata audit events.
There is no audio ingestion, ASR, note generation, approval, or export yet.
No models or datasets have been downloaded or benchmarked.

## Run locally

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

Creation does not authorize recording. Record scopes separately through
`POST /v1/encounters/{id}/authorizations`, with `scopes`, `policy_version`,
`method`, and a future timezone-aware `expires_at`. The permission endpoint
shows effective authorization; inference remains disabled in this milestone.
Withdrawal is repeatable and preserves its original timestamp.

## Verify

```powershell
python -m pytest -q
```

Tests cover access denial, cross-tenant and unassigned-clinician access,
authorization expiry/withdrawal, persistence across restart, transactional
audit records, unsupported configuration, and redacted validation errors.

## Boundaries and next work

This development service uses operator-provisioned bearer credentials, not a
human SSO/session implementation. SQLite is a development storage choice;
PostgreSQL, schema migrations, encryption, retention controls, immutable audit
storage and deployment hardening are required before a real-data pilot.
`synthetic_data: true` is an explicit developer attestation, not a detector of
patient information. Do not enter real patient information.

See [implementation status](docs/implementation-status.md) for the staged backlog.
Commit and push verified milestones to the configured GitHub remote; never
commit credentials, databases, recordings, or private annotations.
