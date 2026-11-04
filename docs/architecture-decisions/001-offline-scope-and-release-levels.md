# ADR 001 — Offline research scope and independent release levels

Accepted for the zero-external-input engineering programme. Version 1 is English-only, local-first and synthetic/public-mock only. Imaging, multilingual expansion, MRI/X-ray and TTS remain future research ideas; they are excluded from this critical path without deleting historical plans.

Four release dimensions are mandatory: `offline_demo`, `engineering_verified`, `research_evidence_complete`, `clinical_approved`. Successful software checks cannot imply clinical admission. Clinical release stays `BLOCKED_EXTERNAL_EVIDENCE_REQUIRED`; `real_patient_release_authorized=false` is mandatory in acceptance artifacts.

The 5% normalized WER gate is unchanged. Frozen protocols and report bytes retain their hashes. New parameters, wrappers or recovery policies require a new protocol and output path. Each failed recording retains the specified whole-reference deletion penalty. Unfinished and negative runs remain separately published.

Alternative rejected: one `ready=true` flag obscures engineering, data and clinical dependencies. Alternative rejected: lowered WER thresholds or removing uncertain reference words would change the question after seeing results. Existing reference uncertainty remains a secondary diagnostic only.

Evidence hierarchy, highest to lowest: (1) independently adjudicated clinical labels from qualified reviewers; (2) non-independent upstream source references; (3) developer-authored synthetic oracles; (4) model judgments. No current developer-generated report may impersonate a higher tier. No independent clinical reviewers or new clinical data are introduced by this programme.

The offline guard denies external Python DNS/TCP/UDP and constrains provider configuration; it is not an operating-system firewall or a guarantee about arbitrary native subprocesses. A true isolated packaging or native network claim must be tested separately. Missing model assets, tooling, cached wheelhouses and external evidence are named blockers, not simulated passes.
