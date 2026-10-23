# Development operations and recovery

The application remains synthetic-only. SQLite and the development PostgreSQL
configuration are not encrypted by this app. Protect devices, volumes, keys and
backups separately. Production SSO, database row-level policy, encryption/key
management, independent security review and clinical/governance sign-off remain
release prerequisites; the development access key is not production identity.

## Local workstation

Run `./scripts/start.ps1` from Windows. It creates an isolated Python environment,
installs media support, builds the UI, generates an audible synthetic example
where a system speech voice is installed, and starts the loopback API plus a
separate worker. Add `-WithAsr` for local speech dependencies. Set
`MED_TRANSCRIPT_ASR_PROFILES` to an operator-created local profile file to enable
speech jobs. The access key is printed at startup and kept in ignored
`data/local-config.json`; treat that file as a credential. Stop the launcher with
Ctrl+C so it terminates its worker. Browser keys stay in memory, not local storage.

The worker polls ingest and ASR queues and periodically processes eligible
unapproved encounter deletion requests. It preserves explicit failure/cancellation
status. A later source correction fences late ASR output. If the worker stops,
API review remains available; restart it to recover expired leases. Do not
silently change models, devices or providers to recover a failure.

## Media boundary

WAV, MP3, M4A/MP4 audio, WebM audio and Ogg have explicit MIME contracts.
The decoded container must match the declared type; video or multiple audio
streams are rejected. Originals retain their upload checksums. Non-mono/non-16k
or compressed inputs are normalized in a separate process using PyAV, with a
120-second parent timeout and bounded 60-minute PCM output. Unix additionally
limits CPU time, output file size and address space. Child environments omit
application/provider credentials; decoder stderr is discarded.

Each attempt writes its own staging output. Only a valid lease and current
authorization can publish the normalized asset. Source and working hashes are
checked again by ASR. Normalized media timing is marked for source review;
resampling does not establish clinically accurate alignment. Windows has process
isolation/timeouts but no per-child kernel memory sandbox here. Audit native codec
and OS containment before untrusted real-data deployment. Container deployment
adds read-only roots, memory/CPU/pid bounds, dropped capabilities and no external
runtime network; these controls still require deployment testing.

## Backup and restore (SQLite)

```powershell
python -m services.maintenance integrity
python -m services.maintenance backup --destination data/backups/snapshot-001
python -m services.maintenance restore --source data/backups/snapshot-001 --destination data/recovery-001 --tombstones-from data/development.sqlite3
```

Backup uses SQLite's backup API with committed-asset copying under the application
write lock. It writes checksums and identifies an incomplete backup. Destinations
must be new directories. These are **plaintext** snapshots: keep them on protected
encrypted storage and apply a separately approved retention schedule.

Restore verifies every recorded checksum and rejects escaping manifest paths.
Supply the latest protected live/tombstone database so deletions after the
snapshot remain inaccessible after restore. The restored copy is for operator
review; do not point the application at it until integrity, tombstones, credentials,
model paths and pending jobs are checked. Test this recovery on synthetic data.
Loss of the newest tombstone ledger cannot be repaired from an older backup alone.

## Deletion, holds and interrupted uploads

An authenticated deletion request immediately tombstones an unapproved encounter,
blocks reads/new processing, and cancels jobs. Legal holds and approved medical
records require retention review and cannot use this generic deletion path.
The worker removes permitted primary rows/assets, preserving restricted audit
metadata, and reports `primary_purged_backups_pending`. It never claims every
backup or filesystem remnant has been erased. Operators must track backup expiry
and any mandated record-retention/amendment requirements separately.

```powershell
python -m services.maintenance purge
python -m services.maintenance reconcile
python -m services.maintenance reconcile --apply
```

Reconciliation defaults to dry run, recognizes generated filenames only, protects
active transfers/leases and legal holds, and never scans arbitrary external
directories. It cleans abandoned staging assets and eligible expired uploads.
Do not manually edit approved note bodies to fix a record: begin an amendment.

## PostgreSQL and containers

Install `.[postgres]`, set `MED_TRANSCRIPT_DB` to an isolated PostgreSQL DSN and
`MED_TRANSCRIPT_ASSETS` to the shared local asset directory. Application migrations
run transactionally; exact-version transactions use a conservative database-wide
advisory lock in development. This favors correctness over throughput. Tests
cover the real PostgreSQL create/authorization/review/approval path in GitHub CI.
Use PostgreSQL-native `pg_dump`/restore, protected asset snapshots and tombstone
reconciliation for that deployment, not the SQLite maintenance backup command.

With Docker installed, set a random URL-safe `POSTGRES_PASSWORD` and run
`docker compose up --build`. The database port is not published; the UI is bound
to host loopback. App state and PostgreSQL use separate named volumes on an
internal network. Read the local access key from API startup logs. Models are
not included in the image: provision artifacts and profiles in the app volume and
set `MED_TRANSCRIPT_CONTAINER_ASR_PROFILES` to its container path before restart.
Containers are a development deployment, not an automatic compliance assertion.
Docker was unavailable on the authoring workstation; the image build is checked
in CI, while runtime host/GPU hardening remains an operator acceptance task.
