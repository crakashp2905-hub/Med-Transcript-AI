# Product scenarios, support, and launch controls v1

This document supports internal planning. The scenarios, workflows, and feedback below are simulations. They do not represent observed customers, clinical outcomes, purchase intent, market size, or approved deployment.

## 21. Hypothetical business scenarios

| Scenario | Hypothetical users and workflow | Cost drivers | Unvalidated decision |
|---|---|---|---|
| Individual clinician | One clinician uses one verified workstation for English encounter review | Hardware amortization, electricity, support time, any measured local model cost | Whether the workflow fits the clinician’s practice and whether the clinician would adopt it |
| Small clinic | Five clinicians share three workstations and an administrator supports setup | Shared hardware, local energy, support/training, retention and identity controls | Whether shared-device operations and clinic governance are acceptable |
| Institution | Fifty clinicians use twenty-five managed workstations under institutional IT and clinical governance | Managed hardware, support staffing, security assessment, retention, integration and monitoring | Whether procurement, privacy, security, clinical, and operational owners approve a scoped pilot |

The unit-economics workbook uses illustrative cost inputs for these configurations. No scenario includes revenue, an assumed price, market-size estimate, paying-demand claim, or expected return. Replace assumptions only with quotes, measured usage, or institution-provided data, and label the source and date.

## 22. Release notes, change log, FAQ, and escalation

### Release note template

- **Version and source commit:** record the exact release identifier.
- **What changed:** describe user-visible workflow changes.
- **What was verified:** list exact-commit automated checks and the tested support matrix.
- **Known limits:** identify unavailable models, languages, devices, external approvals, and unresolved clinical evidence.
- **Data handling:** state the selected local/hosted mode, retention configuration, and export behavior.
- **Upgrade or rollback:** give the operator’s tested steps and data-preservation conditions.

### Change log policy

Keep dated entries for user-visible behavior, compatibility, data migrations, security changes, model/runtime changes and known issues. Bind each entry to a commit. Keep failed, reverted, or blocked releases visible; do not relabel a failed acceptance as a release.

### Support FAQ

- **Can this sign a note automatically?** No. AI proposals remain separate until an authorized clinician approves the exact version.
- **Does the demo prove clinical accuracy or time savings?** No. Synthetic and scripted walkthroughs test software behavior only.
- **What if a model is missing?** The workflow must show it as unavailable. Do not download weights or substitute another model without authorization.
- **What if recording or inference fails?** Preserve the source and use the institution’s existing approved documentation workflow. Do not upload patient data to this prototype.
- **Is the FHIR export certified for an EHR?** No. It produces a prototype R4 DocumentReference; receiving-system profiles and integration are unverified.
- **Can a clinician use real patient data now?** No. Real-patient release and pilot approval are not authorized.

### Escalation playbook

1. Stop capture/export if consent, identity, source integrity, approval version, or data-flow mode is uncertain.
2. Preserve the original audio and append-only logs; do not overwrite or manually edit stored evidence to restore a green status.
3. Record the local error code, source/note version identifiers, model/profile digest, time, and operator action. Avoid copying patient text into general support channels.
4. Route authentication or access issues to the institution’s identity/security operator; storage/retention issues to the designated privacy/security owner; model/runtime failures to the technical operator; clinical content issues to a qualified clinician.
5. Resume only after the owner confirms recovery conditions and the application rechecks version, consent, and integrity gates.

### User-visible model limitations

ASR can omit or alter words, medications, doses, negation, timing, and speaker attribution. Local or hosted drafting may omit facts or add unsupported claims. Timestamps and citations help review but do not establish that a statement is clinically correct. Human review is required. The 5% normalized-WER admission threshold remains unmet for the current eligible full-conversation evidence. No model output independently diagnoses or prescribes.

## 23. FHIR R4 export boundary

The application serializes an approved note as a FHIR R4 DocumentReference with an inline JSON attachment. The resource carries the note identifier, an identifier derived from the approved note digest, current/final status, approval date, encounter identifier, and the approved note/evidence content. Serialization and identifier integrity are exercised by tests/test_presentation_tools.py and workflow tests. The implementation does not create a coded MedicationRequest or AllergyIntolerance, submit a FHIR transaction, write to an EHR, validate against a receiver-specific profile, or confer EHR certification. Any receiving integration needs separate profile validation, authorization, and end-to-end testing.

## 24. Buyer privacy and security checklist

### Buyer review checklist

- Identify controller/processor roles, intended use, deployment country, legal basis, consent process, and data-subject rights.
- Map audio, transcript, note, evidence, audit, identity, backup, and export data with location, owner, retention period, and deletion procedure.
- Confirm local versus hosted inference, network egress, telemetry, provider terms, model licensing, subprocessors, encryption, and key ownership.
- Review authentication, role authorization, tenant boundaries, audit access, session expiry, secrets, incident response, vulnerability handling, and backup/restore.
- Verify workstation, browser, microphone/interface, channel count, operating system, memory, model digest, and failure/recovery behavior against the exact support matrix.
- Approve retention, backup, deletion, export, and incident procedures before pilot data is loaded.
- Record a qualified clinical owner, privacy/security owners, IT operator, support owner, and escalation contact.
- Review clinical evidence, independent annotations, known limitations, and intended pilot endpoints. Missing evidence remains unknown.

### Deployment dependencies

| Dependency | Required owner | Required evidence before pilot |
|---|---|---|
| Identity and access | Institution identity/security operator | Approved provider registration, role map, access review |
| Hardware and audio | Institution IT/audio operator | Named device/interface and multi-channel physical test record |
| ASR/drafting models | Technical operator and institutional procurement | Locally available model digests, license/access approval, measured resource profile |
| Storage and retention | Privacy/security owner | Location, encryption/key ownership, retention and deletion tests |
| EHR interface | Institution integration team | Receiver profile, sandbox credentials, serialization and end-to-end test |
| Clinical review | Qualified clinical owner | Approved protocol, adjudicated cohort, escalation and incident review |

### Data-flow diagram

Clinician and consent → audio capture → preserved source and transcript → evidence-linked extraction → unapproved note proposal → deterministic and independent verification → clinician review and correction → explicit version-bound approval → approved note → serialized export → receiving system only after integration approval.

Audio, extraction, proposal, review, and approval events also feed audit and retention controls. This is a logical product flow, not a claim that institutional identity, network, EHR, or deployment controls are configured.

### Operator responsibilities

Operators configure the approved mode, verify the exact hardware/model inventory, protect credentials, monitor storage and job queues, run backup/restore and deletion procedures, review access/audit events, communicate failures, and stop unsafe or unapproved workflows. Operators cannot provide clinical approval on behalf of a clinician or change model/source evidence to clear an approval gate.

## 25. Investor demo deck outline

1. **Problem hypothesis:** documentation burden and review friction are proposed problems; demand is unvalidated.
2. **Product concept:** English encounter documentation with source-linked proposals and explicit clinician approval.
3. **Synthetic walkthrough:** open audio/transcript, inspect evidence, correct the deliberate dose mismatch, review approval and provenance.
4. **Safety boundary:** proposals are separate from approved notes; source edits invalidate dependent approval; missing models are unavailable.
5. **Architecture:** local-first path, optional adapters, audit/version controls, and data-flow choices.
6. **What is measured:** exact-commit software checks, synthetic cases, available benchmark reports, costs under stated assumptions.
7. **What is not measured:** independent clinical accuracy, clinician time savings, physical hardware coverage, purchasing demand, and EHR certification.
8. **Roadmap and dependencies:** full-length ASR, independent annotation, speaker attribution, hardware, security, and institution approvals.
9. **Hypothetical economics:** use the unit-economics workbook’s three editable scenarios; inputs are not quotes or demand forecasts.
10. **Ask and open questions:** identify the specific reviewer, institution, device, and approval dependencies sought; do not imply pilot authorization.

Use only reproducible synthetic material and source-audited evidence. Label every simulation, research result, external validation item, and open dependency separately.

## 26. Simulated feedback log and reprioritization rules

The following entries are test scenarios, not customer comments, interview findings, or user quotes.

| Scenario ID | Simulated workflow signal | Product response | Evidence status |
|---|---|---|---|
| SIM-FB-01 | Reviewer cannot tell whether a displayed statement is sourced | Keep evidence link adjacent and add source navigation | Synthetic usability scenario only |
| SIM-FB-02 | A dose mismatch appears below routine warnings | Keep critical severity grouping and require review | Synthetic challenge only |
| SIM-FB-03 | Model is unavailable on first run | Show exact missing dependency and manual fallback | Local diagnostics behavior; hardware readiness untested |
| SIM-FB-04 | Transcript edit leaves an old approval visible | Invalidate dependent proposal and approval version | Software invariant; verified only in listed automated tests |
| SIM-FB-05 | Export lacks receiver-specific profile | Show prototype format and block certification claim | EHR integration not tested |

Reprioritization rule: score evidence-backed harm and workflow impact first, then effort and dependency. A simulated signal may create a research question but cannot be counted as demand or usage. Promote a roadmap item only after its evidence class and owner are recorded. Clinical safety issues can stop a release regardless of RICE score.

## 27. Roadmap scorecard

| Capability | Feature maturity | Usage simulation | Research evidence | External clinical/purchaser validation |
|---|---|---|---|---|
| Evidence-linked review | Implemented in prototype; automated workflow checks exist | Synthetic walkthrough only | Developer-authored fixtures; no independent gold | Not performed |
| ASR full-consultation quality | Candidate integration and local benchmarks exist; 5% gate unmet | Scripted and public/mock recordings only | Benchmark evidence is incomplete and failure-inclusive ranking remains required | Not performed |
| Speaker attribution | Development alternatives and channel analysis exist | Synthetic/channel fixtures | No independent role annotations | Not performed |
| Verification | Rules, evidence graph, and challenge fixtures exist | Synthetic cases only | No qualified independent adjudication | Not performed |
| Clinician timing | Instrumentation and simulated timers exist | Simulated action events | No observed clinician study | Not performed |
| EHR handoff | R4 DocumentReference serializer exists | Local serialization tests | Receiver profile not validated | No certification or partner validation |
| Local/hardware deployment | Local demo path exists | Emulated/headless environment | Narrow support matrix only | Physical device and institution reviews not performed |

Do not combine maturity, simulated usage, research evidence, and external validation into a single readiness score. Keep unknown categories visible.

## 28. Launch decision policy

An AI agent may summarize evidence and recommend that a scoped pilot review begin. It cannot authorize real-patient processing, approve a clinical pilot, certify clinical benefit, approve a regulated use, or substitute for institutional decision-makers. Real-patient processing remains blocked until qualified clinical ownership, independent acceptance evidence, security/privacy approval, named hardware and deployment validation, incident/retention procedures, and institutional sign-off are documented. A recommendation is not an authorization. The current project does not meet those gates.
