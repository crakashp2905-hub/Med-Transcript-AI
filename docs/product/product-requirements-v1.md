# Med-Transcript AI product requirements v1

**Status:** internal product hypothesis, suitable for prototype planning only  
**Scope:** English-language clinician-supervised encounter documentation  
**Evidence boundary:** all personas, workflow observations, demand, prioritization inputs, and targets below are internal assumptions or simulations. No customer interviews, clinician timing study, clinical validation, purchase intent, EHR certification, or pilot approval is represented.

## 1. Product requirements and job to be done

**Job to be done:** When a clinician completes an English consultation, help them review and correct a structured encounter note faster and with clearer source traceability, so they can approve an accurate record while retaining control over every clinical claim.

The prototype must keep a visible chain from available audio and transcript to extracted facts, draft statements, warnings, corrections, and the clinician-approved version. It must identify missing or uncertain evidence, preserve revisions, and prevent an AI proposal from becoming an approved note without an explicit clinician action. A failed, incomplete, or unavailable model must be shown as unavailable; it must not produce a fabricated success state.

### User and system outcomes

- The clinician can inspect the source beside the transcript, draft, evidence, and verification findings.
- Each proposed clinical statement can be traced to source evidence or marked unsupported/uncertain.
- Medication, allergy, negation, speaker attribution, temporality, and omission risks receive clear review attention.
- The clinician can edit, reject, and approve a version; source edits invalidate dependent proposals and approvals.
- A local demo can be completed with synthetic data and no external model call.
- Real-world speed, accuracy, harm reduction, and willingness to pay remain unknown until measured with qualified reviewers and intended users.

## 2. Explicit non-goals

Version 1 does not provide autonomous diagnosis, prescribing or treatment decisions; unsupervised patient-facing deployment; radiology, MRI, or X-ray interpretation; multilingual recognition; text-to-speech; replacement of the clinician or medical record; automatic signing or export approval; or claims of clinical benefit, regulatory clearance, EHR certification, or production availability. Any extension requires separate product, safety, privacy, and evidence review.

## 3. Synthetic personas (assumptions, not research participants)

| Persona | Assumed goal | Main concern | Prototype need |
|---|---|---|---|
| General physician | Finish a complete encounter note with less after-visit work | Wrong dose, negation, or patient attribution | Evidence-linked draft, critical warnings, fast edit and approval |
| Clinical scribe | Organize the conversation without changing its meaning | Lost source context and unclear corrections | Timestamp navigation, speaker labels, revision history |
| Practice administrator | Keep the workflow usable and supportable | Setup, queue delays, failed exports | Readiness/status view, recoverable errors, export integrity |
| Compliance officer | Understand data movement, access, retention, and audit | Hidden external calls or untracked access | Data-flow disclosure, access/audit records, retention controls |
| Patient records recipient | Receive a readable, corrected record | Incomplete or confusing documentation | Clinician-approved output and clear correction path |

These profiles are design prompts, not validated user segments.

## 4. End-to-end job map

| Stage | User job | Product support | Failure or trust condition |
|---|---|---|---|
| Pre-visit | Select an encounter and confirm readiness | Show supported mode, model availability, consent and storage state | Do not imply recording or inference is ready when it is not |
| Recording | Capture the visit with consent | Show recording state, elapsed time, interruption and recovery status | Preserve the original audio; disclose gaps and channel limits |
| During visit | Continue the consultation without managing a complex UI | Keep controls simple; expose status and safe pause/stop | No fabricated live result; visible buffering and failure state |
| Review | Check transcript, speakers, note claims and evidence | Source navigation, timestamps, confidence/uncertainty, severity-grouped warnings | Unlinked or low-confidence claims stay unapproved |
| Correction | Repair transcript or note while preserving provenance | Version corrections and invalidate dependent evidence/approvals | Stale approvals cannot survive changed source or content |
| Sign-off | Approve the exact reviewed version | Explicit clinician action, identity and version binding | AI proposals remain separate from signed/approved notes |
| EHR handoff | Export or transfer the approved record | Validate serialization and identifiers; show completion/failure | No claim of EHR certification; failed export is not success |

## 5. Testable problem hypotheses

All statements below are internal assumptions pending interviews and observation.

1. **H1 — Review time:** Evidence navigation and structured corrections may reduce active correction time compared with a manual note workflow. Test with a preregistered paired study and qualified clinicians; do not infer from software timings.
2. **H2 — Error discovery:** Severity-grouped verification may help reviewers find critical medication, negation, attribution, or omission errors. Test against independently adjudicated cases and count misses and false alarms.
3. **H3 — Trust calibration:** Visible uncertainty and source links may help reviewers distinguish supported from unsupported claims. Test with blinded review tasks and predeclared trust-calibration measures.
4. **H4 — Operational fit:** A local-first workflow may fit environments that restrict external processing. Test setup, device compatibility, latency, security controls, and operator burden with the intended institution.
5. **H5 — Adoption:** Clinicians or institutions may value reduced documentation burden enough to adopt the workflow. This remains untested; only interviews and observed workflow studies can evaluate it.

## 6. Customer journey and trust friction

| Moment | Likely friction (assumption) | Required product response |
|---|---|---|
| Setup | Unknown device, model, or permission state | Preflight checklist and manual documentation fallback |
| Start | Consent or recording status is ambiguous | Clear consent/readiness state and visible recording control |
| Conversation | Noise, overlap, or long duration may degrade recognition | Preserve audio, show coverage/gaps, allow retry without losing source |
| Draft wait | Latency and unavailable models create uncertainty | Stage-by-stage progress, timeout, cancellation, retry and no false green |
| Review | Transcript errors may look plausible | Timestamped source playback, linked evidence and critical warning grouping |
| Correction | Edits may leave stale derived text or approval | Recompute/invalidate dependencies and show version changes |
| Export | Users may confuse generated output with an approved record | Require clinician approval and report export state and format limits |

## 7. User stories and acceptance examples

These are prototype acceptance requirements, not evidence of usability or clinical performance.

1. **As a physician**, I need to see whether the encounter is ready so that I do not start a workflow with missing dependencies. **Given** a required local model is absent, **when** I open readiness, **then** it says unavailable and offers the documented manual path.
2. **As a physician**, I need a clear consent state so that recording does not begin ambiguously. **Given** consent is not recorded, **when** I try to start, **then** capture is blocked and the missing action is explained.
3. **As a scribe**, I need a recording indicator so that I know capture is active. **Given** capture starts, **when** audio is being recorded, **then** state and elapsed time remain visible.
4. **As a physician**, I need recoverable interruption handling so that an interruption does not silently discard source. **Given** capture or processing is interrupted, **when** the workflow resumes, **then** preserved and missing ranges are distinguished.
5. **As a scribe**, I need timestamped transcript segments so that I can locate the source. **Given** a transcript segment has valid timestamps, **when** I select it, **then** source playback seeks to that interval.
6. **As a physician**, I need speaker labels to remain provisional until confirmed so that an uncertain voice is not asserted as a role. **Given** role confidence is inadequate, **when** the draft is shown, **then** the speaker is marked for review.
7. **As a physician**, I need each clinical statement linked to evidence so that I can verify it. **Given** a supported statement, **when** I inspect its citation, **then** the source interval and text are available.
8. **As a physician**, I need unsupported claims surfaced so that generated additions do not pass as facts. **Given** a claim lacks evidence, **when** verification runs, **then** it is flagged and cannot be approved silently.
9. **As a physician**, I need medication and dose issues grouped prominently so that high-impact errors are easy to inspect. **Given** a dose mismatch exists, **when** warnings are shown, **then** the issue appears in the critical group with source navigation.
10. **As a physician**, I need negation scope preserved so that “no allergy” is not changed into an allergy. **Given** source and draft polarity differ, **when** verification runs, **then** approval is blocked pending review.
11. **As a physician**, I need allergy reactions retained so that the note does not omit material reaction details. **Given** an allergy reaction is in the source, **when** it is missing from the draft, **then** an omission finding points to the source.
12. **As a physician**, I need patient and family facts separated so that family history is not attributed to the patient. **Given** speakers or subjects differ, **when** claims are compared, **then** attribution disagreement is visible.
13. **As a physician**, I need planned and completed events distinguished so that intent is not documented as completion. **Given** temporal status differs, **when** the draft is checked, **then** the mismatch is reviewable.
14. **As a physician**, I need to correct a transcript segment so that downstream content reflects the correction. **Given** a cited source segment changes, **when** dependent proposals are refreshed, **then** old citations and approvals are invalidated.
15. **As a physician**, I need to reject an AI proposal so that rejected text never becomes approved content. **Given** a proposal is rejected, **when** I approve the note, **then** that proposal is absent from the approved version.
16. **As a physician**, I need version-bound approval so that edits cannot inherit stale approval. **Given** the note changes after approval, **when** status is viewed, **then** the changed version requires review again.
17. **As an administrator**, I need recoverable retries so that transient failures do not corrupt an encounter. **Given** processing fails, **when** retry is offered, **then** it uses the preserved source and records a new attempt.
18. **As a compliance officer**, I need a visible data-flow mode so that local and hosted processing are distinguishable. **Given** a local-only demo is selected, **when** it runs, **then** the interface and audit record disclose the mode and provider calls remain absent.
19. **As a physician**, I need a readable approved export so that the final record can be handed off. **Given** an approved version exists, **when** export is requested, **then** identifiers and version references are preserved and export failure is explicit.
20. **As a patient records recipient**, I need corrections to be attributable so that I can understand which record version was issued. **Given** a correction is approved, **when** a replacement export is produced, **then** it has a distinct version and audit trail.

## 8. Feature inventory

| Priority | Features |
|---|---|
| Must have | Consent/readiness disclosure; source preservation; transcript timestamps; evidence-linked proposals; severity-grouped verification; edit/reject/approve separation; immutable version binding; recoverable failures; explicit export state; local demo with synthetic data |
| Should have | Multi-channel input when hardware supports it; clinician-confirmed speaker roles; source playback from citations; interruption/retry workflow; retention controls; audit review; configurable local drafting adapter |
| Could have | Institution-specific templates; configurable terminology lists; validated integrations; workflow analytics based on consented, deidentified operational data |
| Excluded from v1 | Autonomous diagnosis/prescribing; unsupervised patient use; radiology; multilingual ASR; TTS; automatic note signing; claims of clinical-grade accuracy; unapproved hosted inference |

## 9. Simulated prioritization (RICE)

Scores below are hypothetical inputs used to demonstrate a transparent method. They are not market research, customer counts, measured impact, or delivery estimates. Formula: `reach × impact × confidence ÷ effort`; reach is assumed affected workflow share on a 1–10 relative scale, impact is 1–3, confidence is 0.1–1, and effort is relative person-weeks.

| Feature | Reach | Impact | Confidence | Effort | Simulated RICE | Why it ranks here |
|---|---:|---:|---:|---:|---:|---|
| Evidence-linked review | 8 | 3 | 0.7 | 4 | 4.20 | Central to trust and correction; still needs user validation |
| Critical warning review | 7 | 3 | 0.6 | 5 | 2.52 | High harm relevance; false alarms and misses need evaluation |
| Version-bound approval | 6 | 3 | 0.8 | 5 | 2.88 | Core safety invariant with testable behavior |
| Interruption and retry recovery | 6 | 2 | 0.6 | 4 | 1.80 | Protects work continuity; usage frequency unknown |
| Configurable template | 5 | 2 | 0.4 | 5 | 0.80 | Potential workflow fit; institutional needs unknown |
| EHR integration | 4 | 3 | 0.2 | 12 | 0.20 | High dependency and certification burden; defer until partner requirements exist |

These simulated values must be replaced with observed research and engineering estimates before investment decisions.

## 10. Risk-adjusted roadmap

| Order | Workstream | Product value | Clinical harm if wrong | Effort/dependency | Exit evidence |
|---:|---|---|---|---|---|
| 1 | Preserve source, version state, evidence links, approval gates | Foundational review workflow | High | Medium; current code and synthetic tests | Exact-version and provenance tests pass |
| 2 | Improve English consultation ASR and timestamp coverage | More complete draft input | High | High; local models/data and reviewer labels | Frozen full-consultation evaluation, failure-inclusive and below the 5% gate before admission |
| 3 | Evaluate medication, negation, attribution, omission verification | Safer review attention | Very high | High; independent qualified annotation needed for clinical claims | Blinded challenge and independent acceptance cohort; misses and false alarms reported |
| 4 | Test long recordings, interruption, retries, browser/hardware | Usable session workflow | Medium/high | Medium; device and OS matrix | 20–30 minute workflow and physical hardware evidence |
| 5 | Validate timing and correction burden with clinicians | Productivity evidence | High | External reviewer dependency | Paired observed study; simulated timing kept separate |
| 6 | Pilot security, retention, support, and integrations | Deployment readiness | Very high | Institution, legal/privacy and IT owners | Written institutional approvals and operational controls |

No milestone authorizes real-patient processing. Work requiring independent reviewers, hardware, model assets, institution approval, or credentials remains gated until those inputs exist.

## 11. Product promise and validation boundary

The proposed product promise is: **traceable evidence, immutable versions, conservative review, local-first privacy options, and clinician approval.** It is a design commitment, not a measured competitive advantage. It may be used for an internal synthetic prototype walkthrough. Any investor or buyer presentation must label measured engineering behavior separately from research evidence, simulated usage, and unvalidated commercial assumptions.
