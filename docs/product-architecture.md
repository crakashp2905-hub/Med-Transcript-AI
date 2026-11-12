# Product architecture and evidence map

This page is the investor-demo architecture map for the local-first prototype.

```mermaid
flowchart LR
  A[Loopback browser audio] --> B[Scoped ingest + hash]
  B --> C[Immutable transcript versions]
  C --> D[Evidence-linked typed facts]
  D --> E[Deterministic note baseline]
  D --> F[Optional local model proposal]
  E --> G[Independent verification]
  F --> G
  G --> H[Clinician correction + exact-version approval]
  H --> I[Attributed exports]
```

## Encounter sequence

This sequence documents the application boundaries. Model output remains a
proposal; an export can be created only from a clinician-approved exact note
and transcript version.

```mermaid
sequenceDiagram
  actor Clinician
  participant UI as Clinician browser
  participant API as Scoped API
  participant Store as Encounter store
  participant Queue as Job queue and worker
  participant ASR as Timestamped ASR
  participant Extract as Fact and relationship extraction
  participant Evidence as Evidence graph validator
  participant Draft as Note drafter
  participant Verify as Independent checks
  participant Review as Clinician review and approval
  participant Export as Export service

  Clinician->>UI: Authenticate, create encounter, grant processing consent
  UI->>API: Create scoped encounter and upload reservation
  API->>Store: Persist encounter, consent and authorization
  UI->>API: Upload audio chunks and seal byte count plus SHA-256
  API->>Store: Persist immutable audio asset and integrity receipt
  UI->>API: POST /transcriptions
  API->>Queue: Enqueue authorized transcription job
  Queue->>Store: Claim job with bounded lease
  Queue->>ASR: Normalize audio and transcribe with selected local profile
  ASR-->>Queue: Timestamped segments, profile receipt, or explicit failure
  Queue->>Store: Append immutable transcript version with source hash
  UI->>API: Read transcript and request POST /fact-proposals
  API->>Extract: Extract typed facts and relationships from selected segments
  Extract-->>API: Candidate facts with evidence references
  API->>Evidence: Validate exact source spans, version and relation tuples
  Evidence-->>API: Validated proposal or reject the entire invalid result
  UI->>API: POST /draft-proposals using validated facts
  API->>Draft: Apply deterministic template baseline
  opt Authorized local drafting adapter enabled
    API->>Draft: Request optional model draft as a separate proposal
  end
  Draft-->>API: Note proposal; never an approved note
  UI->>API: POST /semantic-checks for current note and transcript versions
  API->>Verify: Check claims, omissions and evidence relationships
  Verify-->>API: Findings and advisory model output; cannot approve or clear gates
  API-->>UI: Show audio, transcript, note proposal, citations and warnings
  Clinician->>UI: Play cited source, correct note and resolve review findings
  UI->>API: PATCH /notes/{id}
  API->>Store: Append a new unapproved note version; stale prior checks
  Clinician->>UI: Review the saved exact versions and approve
  UI->>Review: POST /approvals with transcript, note and verification hashes
  Review->>Store: Verify current hashes and blocking findings, then seal approval
  Store-->>Review: Approval receipt bound to exact versions
  Clinician->>UI: Request an export for the approved note
  UI->>Export: POST /exports with approval ID and format
  Export->>Store: Recheck approval, source and note integrity
  Export-->>UI: Return attributed export and digest
```

An interrupted upload cannot start transcription until its bytes are sealed.
Retries use the existing job lease and source identity. A changed transcript
or note makes dependent proposals, checks or approvals stale. AI-generated
content never replaces the clinician-approved note.

## API examples

```http
GET /health
GET /v1/encounters/{encounter_id}/workspace
PATCH /v1/encounters/{encounter_id}/notes/{note_id}
POST /v1/encounters/{encounter_id}/approvals
POST /v1/encounters/{encounter_id}/exports
```

Every write is scoped to the tenant, clinician, encounter and current immutable
version. Approval requires the current note hash and verification receipt.

## Data lifecycle

Audio is ingested with a checksum, normalized into a separate working asset,
transcribed into immutable versions, converted into evidence-linked facts, and
drafted as a proposal. Verification findings remain blocking until a clinician
reviews and corrects them. Only an exact-version approval can produce exports;
amendments create a new version. Retention purge and backup expiry are separate
operator actions.

## Security and limitations

The [local threat model](local-threat-model.md) covers browser audio, workers,
prompts, model outputs, notes, exports and backups. The [runtime support
matrix](runtime-support-matrix.md) and [model-selection notes](model-selection.md)
document tested environments and model limits. All benchmarks retain failures,
the unchanged 5% normalized-WER gate, and `real_patient_release_authorized=false`.
This is not a clinical approval, compliance certification, independent clinical
study, or live Google/OIDC deployment.

## Model cards and reports

Dataset-specific cards are generated from the frozen reports in
`evaluation/reports/` and must retain language, runtime, decoding, failures,
timeouts, WER, role metrics and limitations. The [evaluation protocol](evaluation-protocol.md)
defines the source-of-truth and admission rules; hosted and missing-artifact
models remain visible but unranked or blocked.
