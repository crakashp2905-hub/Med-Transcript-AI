# Product modes, onboarding, and measurement v1

All targets and behavior below are product requirements or simulations. They are not observed clinical outcomes, customer commitments, production SLOs, or deployment approvals.

## Product promise

Proposed differentiation: traceable evidence, immutable versioning, conservative safety behavior, local-first privacy options, and explicit human approval. The promise is testable as software behavior; superiority, clinical value, and commercial differentiation are not established.

## Packaged modes

| Mode | Audience | Data and capabilities | Approval boundary |
|---|---|---|---|
| Local synthetic demo | Internal reviewers and investors | Preinstalled synthetic consultation, local scripted workflow, no external provider call | Read-only or synthetic clinician workflow; no real patient data |
| Clinician workstation candidate | Qualified clinician in an approved environment | Local capture and inference only when the exact supported hardware and assets are present | Every note remains a proposal until explicit clinician approval |
| Read-only investor | Investors and product reviewers | Synthetic, static walkthrough and preapproved engineering evidence | No capture, note editing, patient data, or implied clinical validation |
| Institution pilot candidate | Named institution after its approvals | Only institution-configured workflow, identity, retention, security, and integration scope | Blocked until institutional, clinical, privacy, security, and operational sign-off |

Modes are capability and data-flow boundaries, not a claim that all modes are currently deployable.

## Zero-assumption onboarding and manual fallback

1. Confirm the operating system, browser, microphone/interface, account role, storage location, and supported-model inventory against the published local support matrix.
2. Run preflight; show every missing dependency, permission, model, or service as unavailable. Do not install or download anything during the workflow.
3. Select synthetic demo or an explicitly authorized workstation mode. Display data-flow and retention settings before capture.
4. Complete consent and microphone checks before enabling recording.
5. Run a short synthetic sound-level check and show channel count, clipping, and silence warnings. This does not certify hardware compatibility.
6. Use the synthetic tutorial before the first real encounter; require a separate institutional decision before any patient data is entered.
7. If capture or inference is unavailable, use the manual workflow: create a note in the institution’s existing approved system, use only institution-approved transcription tools, and do not upload patient material to this prototype. A user may enter a manually prepared synthetic test case for product exploration.

## Product success metric dictionary

| Metric | Definition | Evidence class | Guard against |
|---|---|---|---|
| Case completion rate | Completed eligible cases divided by all eligible started cases; failures remain in denominator | Simulated until qualified users are observed | Exclude neither abandoned nor failed cases |
| Time to first reviewed draft | Wall time from eligible source completion to first clinician-reviewed draft | Software timing is not clinician active time | Do not call it time saved |
| Active correction time | Directly observed clinician active editing/review time per completed case | Unavailable until approved clinician timing study | Self-report and scripted delays are separate |
| Critical warning acknowledgment | Required critical findings explicitly reviewed / all critical findings shown | Simulated until independently adjudicated cases and human study | Acknowledgment is not correctness |
| Export success | Valid exports / all export attempts, including failed attempts | Engineering metric | No EHR certification implied |

## Dashboard measurement classes

Every event must carry `measurement_class`: `simulated`, `software_observed`, `clinician_observed`, or `independently_adjudicated`. It also carries `case_id`, `source_version`, `note_version`, `started_at`, `ended_at`, `complete`, `failure_code`, and an explicit `denominator_eligible` flag. Clinician identity and patient content are not required in aggregate product metrics. Missing values stay null; the system may not convert a simulated click or wall-clock duration into clinician behavior or clinical accuracy.

## Guardrail metrics and stop conditions

- Unsupported critical claims in an approved note: target zero in the synthetic acceptance suite; any occurrence blocks the relevant release candidate.
- Critical omission or polarity/attribution mismatch: report every case and false alarm; do not offset misses with average transcript score.
- Unsafe export or stale approval accepted: target zero; any reproduction blocks release.
- Source citation missing, out of range, or bound to the wrong version: target zero; any reproduction blocks approval for that version.
- Silent truncation or uncovered audio: target zero; report uncovered source intervals and do not declare completion.
- False alerts: count per case and by severity; do not suppress without review evidence.
- Model timeout, queue rejection, and provider failure: count as failures in the applicable denominator; preserve source and provide an explicit safe fallback.

Zero targets here are engineering guardrails to test, not estimates that real-world risk is zero.

## Hypothesis SLOs by hardware tier

These are pre-study hypotheses for local measurement. A tier is not supported until hardware is specified and tested. Targets are not guarantees.

| Hypothetical tier | Example hardware class (not certified) | First status feedback | 30-minute source ingest/validation | Draft stage after source ready | Failure handling |
|---|---|---:|---:|---:|---|
| Workstation candidate | 8+ CPU cores, 16+ GB RAM, supported local model verified by digest | p95 ≤ 1 s | p95 ≤ 30 s | p95 ≤ 120 s | Timeout and cancellation preserve source |
| CPU-only constrained | 4 CPU cores, 8 GB RAM, small supported model verified by digest | p95 ≤ 2 s | p95 ≤ 60 s | p95 ≤ 300 s | Queue backpressure visible; no silent drop |
| Unsupported/unknown | Unknown or absent model, microphone, memory, or browser support | No completion target | Mark unavailable | Mark unavailable | Manual approved-system fallback |

Validation plan: measure at least 30 full synthetic or public-mock runs per supported hardware tier, include failures and queue waits, report p50/p95 and resource use, and separately test 20–30-minute physical recordings. These sample sizes are engineering exploration targets, not statistical or clinical acceptance thresholds. The 5% normalized WER admission gate remains unchanged for ASR evaluation.

## Competitive evidence boundary

No competitor matrix is published in this artifact. The task requires current, source-linked public feature claims; with the local-only research constraint, no external product pages were consulted and no verified local source pack was found in this work. Pricing, trial availability, feature parity, market share, and comparative performance remain unknown.

## Open validation needs

The metric definitions and SLOs require implementation tests, qualified reviewer studies, physical device trials, independent clinical annotation, and institutional security review before they can support external performance or readiness claims.
