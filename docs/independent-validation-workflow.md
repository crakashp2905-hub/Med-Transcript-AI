# Independent validation intake

These tools prepare and analyze human work; they cannot certify credentials, recruit clinicians, approve a pilot or make a failed model pass. Keep public mock recordings as the development source. Do not edit references after seeing model output. Freeze a separate institution-approved acceptance cohort and protocol before measuring acceptance.

The versioned [gold concept schema](../evaluation/gold-concept-schema-v1.json)
defines the clinical vocabulary and exact evidence shape. Workflow validation
also checks these vocabulary enums and the actual source slices; JSON schema
alone cannot validate a citation or prove completeness. Extra flat clinical
slots affect exact matching and must use a frozen agreed vocabulary.

The [reserved acceptance candidate](../evaluation/acceptance-reservation-v1.json)
selects day5 consultations 05–07, disjoint from every current development
manifest. The [source pointer audit](../evaluation/reports/acceptance-source-audit-2026-10-26.json)
records the six upstream audio SHA-256 pointers at the pinned source revision.
It does not claim to have downloaded/audited audio contents. No models have
been evaluated on this reserved cohort. Speakers, sites, devices and training
independence still need audit before it can become an acceptance cohort.

The institution keeps the qualification registry privately, using the fields
listed in the reservation protocol. Verify current credentials, clinical scope,
English consultation experience, conflicts, training and verification dates.
Use a separate training case before blinded annotation; do not train reviewers
on acceptance answers or share the other reviewer's first-pass labels. Stop
and version the source if audible evidence disputes the frozen transcript.
Record uncertainty instead of resolving it through ASR output. The adjudicator
must review all disagreements and audit evidence even when concept labels match.
The code cannot verify identity, qualifications or actual listening.

## Independent annotation

Generate a blank source-only packet, without ASR hypotheses or model-generated facts:

```powershell
.\.venv\Scripts\python.exe -m services.annotation_workflow --out data/reviewer-a.json packet --manifest evaluation/datasets/primock57-full-v1/manifest.json --lock evaluation/datasets/primock57-full-v1/lock.json
```

Generate another fresh copy for reviewer B and distribute each privately. The packet contains all original-timeline reference turns, audio filename/hash and duration. It does not copy audio. Verify audio SHA-256 against the packet and listen to the complete recording. Upstream text is unadjudicated: log disputed source words and stop rather than silently rewriting the frozen reference. A source correction needs a separately versioned, independently reviewed dataset.

Each reviewer supplies a distinct institutional identifier, the three attestations, and completed concept lists for every case. `complete: true` with an empty list explicitly asserts that no concepts apply; it is not proof of completeness. Concept slots follow [clinical annotation instructions](clinical-annotation.md). Each concept also needs a unique `annotation_id` and `evidence` with zero-based `turn_index`, character `start`, exclusive `end`, and exact `quote` in that reference turn. Required clinical slots are `category`, `concept`, `subject`, `assertion`, and `temporality`. Missing clinical information stays unknown. Qualification, independence and actual listening remain externally audited human assertions.

```powershell
.\.venv\Scripts\python.exe -m services.annotation_workflow --out data/disagreements.json compare --first data/reviewer-a.json --second data/reviewer-b.json
```

The comparison uses the same exact clinical-slot matching as the scorer and retains duplicate concept counts. Evidence provenance and annotation IDs do not affect concept matching. Invalid evidence, changed source, missing cases/attestations or reused reviewer identities fail. Agreement never automatically produces clinical gold.

A third qualified adjudicator completes a fresh final packet, adds `review_sha256` from the comparison in the same reviewer order, and adds a `decisions` object mapping every disputed case ID to a written resolution. Reconcile evidence and ambiguity as well as concept differences.

```powershell
.\.venv\Scripts\python.exe -m services.annotation_workflow --out data/adjudicated-candidate.json adjudicate --first data/reviewer-a.json --second data/reviewer-b.json --final data/adjudicator.json
```

Output remains a human-submitted gold candidate until credentials, protocol and source corrections are independently audited. No fabricated reviewer or annotation is bundled. No command overwrites an existing output file.

## Paired clinician study

The clinical owner must preregister case pairing, randomized/counterbalanced task order, reviewer qualifications, correctness adjudication, stopping rules and acceptance thresholds. Pair comparable cases rather than immediately showing the same clinician both versions of one case without accounting for learning. Do not derive independently assessed critical errors from model opinions.

The analysis input contains `protocol_sha256`, a frozen `planned_pairs` list of IDs, and `observations`. Each observation has `pair_id`, `mode` (`manual` or `assisted`), and `status` (`complete` or `failed`). Completed observations require observed nonnegative `wall_seconds` and an independently assessed integer `critical_errors`. Optional `provider_cost` and `hardware_cost` are nonnegative amounts in the protocol's fixed currency; omit unknown costs. Include incurred costs on failed tasks. Do not mix currencies or estimate missing times as zero.

```powershell
.\.venv\Scripts\python.exe -m services.study_analysis --input data/observed-study.json --out data/study-summary.json
```

The summary preserves planned, failed and missing denominators, reports paired median wall-time difference only for completed pairs, and retains negative time savings. Missing cost values produce unknown totals. It does not establish causal productivity, clinical acceptance or verified active time. No real clinician observations have been collected.

## Release evidence inventory

```powershell
.\.venv\Scripts\python.exe -m services.release_readiness --out data/readiness.json --check-release
```

The command rechecks the frozen dataset and recomputes all completed candidate rankings from their reports, records evidence hashes and lists the other unestablished gates. `--check-release` intentionally exits 2 because clinical release remains unestablished. It is separate from engineering CI; passing tests do not waive quality requirements. It never switches application models. The checked-in report is a snapshot, not a live deployment authorization.

Institutional SSO/MFA, encryption/key management, external audit storage, approved retention and backup deletion, security assessment and real-patient approval still require a chosen deployment and its owners. Existing synthetic maintenance/purge routines are not substitutes. No identity provider, production infrastructure or privileged runner has been configured on the user's behalf.
