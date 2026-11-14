# Human study protocol skeleton

**Status:** draft for planning; not approved for recruitment. No participant data or results have been collected.

This draft is a prospective protocol scaffold for a clinician-supervised evaluation of the local English consultation documentation assistant. It is intended to support an item-level crosswalk to DECIDE-AI. The repository has no local copy of the canonical checklist, so the mapping is provisional and exact item-level alignment remains unverified. Do not describe this draft as approved or checklist-compliant.

## Study question and intended use

Define the intended clinical setting, consultation population, documentation task, user, and comparator before choosing outcomes. The system is an English documentation assistant: it may prepare transcript, evidence-linked facts, warnings, and draft text for clinician review. It does not independently diagnose, prescribe, or approve/sign a medical record.

**Primary objective:** `[to be specified before enrollment]`  
**Primary outcome and measurement window:** `[to be specified]`  
**Comparator:** `[to be specified]`  
**Protocol registration/repository:** `[to be specified]`

## Design and setting

Specify prospective/observational or interventional design, sites, dates, workflow stages, unit of analysis, allocation/order if paired, and how interruptions, retries, overrides, and protocol deviations will be recorded. Freeze the system version and comparator before recruitment.

**Design:** `[blank]`  
**Setting and sites:** `[blank]`  
**Target sample size and rationale:** `[blank]`  
**Recruitment and consent:** `[blank]`

## Participants and roles

Document clinician qualifications, years and type of practice, familiarity with the system, training, and any conflicts. Define inclusion/exclusion criteria, recruitment, compensation, and whether patients participate. Patient involvement requires appropriate consent and institutional approval.

**Accountable clinical owner and institution:** `[not identified]`  
**Qualified reviewers:** `[not yet available]`  
**Eligibility and exclusion criteria:** `[blank]`  
**Consent/compensation:** `[blank]`

## System and workflow description

Record the application commit, ASR/model revisions, local hardware and microphone topology, settings, transcript and note templates, warning/verification policy, and any human edits. Describe familiarization and the clinician's ability to pause, correct, reject, or fall back to usual documentation. Preserve each proposed version and distinguish it from clinician-approved content.

**Application commit and model revisions:** `[blank until system freeze]`  
**Audio setup and channel map:** `[blank]`  
**Familiarization:** `[blank]`  
**Fallback and escalation procedure:** `[blank]`

## Outcomes and reference standard

Predefine clinically critical errors, omissions, medication/dose and allergy errors, negation errors, speaker attribution errors, evidence-grounding outcomes, correction time, interruptions, workload, and technical failures. A qualified independent reference and blinded adjudication procedure must be specified where accuracy is evaluated. Keep user experience, process measures, and clinical outcomes distinct.

**Primary/secondary outcomes:** `[blank]`  
**Clinical-critical error taxonomy:** `[blank]`  
**Independent reference and adjudication:** `[blank]`  
**Analysis plan, missingness, and multiplicity:** `[blank]`

## Safety, privacy, and governance

Specify ethics and institutional review, data minimization, access control, retention/deletion, audit, incident and near-miss capture, escalation, independent safety oversight, and stopping rules. No recruitment or patient-data collection should begin before the relevant approvals and qualified reviewers are in place.

**Ethics/institutional approval:** `[not obtained]`  
**Data protection and retention:** `[blank]`  
**Adverse event/near-miss process:** `[blank]`  
**Stopping rules and escalation:** `[blank]`

## Results section (must remain empty until a study is conducted)

- Participants enrolled/completed: **not collected**
- Participant-level outcomes: **none**
- Aggregate outcomes: **none**
- Adverse events/near misses: **not collected**
- Effect estimates or clinical utility claims: **none**

The machine-readable blank protocol is [decide-ai-human-study-skeleton-v1.json](../../evaluation/protocols/decide-ai-human-study-skeleton-v1.json). Its `participant_results`, participant rows, and aggregate results are null/empty. It explicitly records that exact DECIDE-AI checklist alignment is pending access to the canonical checklist.
