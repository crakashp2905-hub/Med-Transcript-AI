# Presentation and review features — 2026-10-29

This release adds the ten prototype features requested after the presentation-readiness discussion. They do not change the 5% normalized WER gate or authorize real-patient use.

| Feature | Available behavior |
| --- | --- |
| Guided demonstration | Five-step walkthrough opens source, note and audit views. Overview offers eight full-length clean public mock consultations (7.6–14.3 minutes), with attribution and verified audio SHA-256 before import. Human reference transcripts are explicitly distinguished from ASR output. |
| Correction view | Current editor versus saved note, including additions, removals, wording and metadata changes. Existing immutable saved-version comparison remains available in history. |
| Completeness checklist | History, medication, allergy, assessment and plan presence, unreviewed counts and evidence-linked navigation. Missing items are not inferred negatives or validated omissions. |
| Uncertainty queue | Critical-detail/unreviewed filters, unknown subjects, uncertain assertions and verification warnings, with links to editable fact cards. Existing severity-based verification remains authoritative. |
| Specialty templates | General practice, respiratory, dermatology and neurology layouts and review prompts over existing SOAP facts. Presentation-only; no inferred examination, reordered underlying facts or automated clinical classification. |
| Encounter timeline | Chronological source turns with speaker/channel labels and click-to-play, plus linked selected facts. Dictation exposes provisional timestamped previews as a live timeline; busy/skipped windows and non-approvability remain explicit. |
| Patient summary | Plain-language headings over exact approved note statements. Clinician can edit wording, separately confirm review and download. Every edit clears confirmation. Note/version, source staleness or dirty editor changes invalidate the summary. Browser review confirmation is not a server-signed approval or delivery to a patient. |
| Structured export | Existing approval-bound JSON plus FHIR R4 DocumentReference with an embedded evidence-linked JSON note and approval. No generated diagnosis codes, medication orders or EHR writes. Recipient-profile validation and institutional integration remain required. |
| Study dashboard | Authenticated current saved ranking, failures/unranked cases, runtime, 5% gate, drafting fixture outcomes and encounter timing sessions. Refresh reloads source reports. Missing reports are explicit nulls. No invented clinical accuracy, verified active time or hardware cost. |
| Recording readiness | Existing input/channel identification plus optional five-second per-channel browser RMS/peak/clipping check. Tracks and audio contexts are released on completion/cancel/unmount/late permission. Audio is not stored or uploaded. Quiet/speech and reconnect checks require actual operator observation. |

## Access

Open the local workspace, sign in using the existing locally stored key, and choose **Open detailed public example** in the overview. Within an encounter use **Start guided walkthrough**, **Facts & SOAP note**, or **Study dashboard**. Expand the review-tool sections to keep the editing workspace compact. Recording readiness is available in dictation after synthetic-recording authorization.

## Scientific and clinical limits

The benchmark campaign continues independently. Its active result files are owned by the campaign and are not rewritten by this feature work. Public examples are development data, not independently adjudicated acceptance cases. Source reference roles and timestamps require review; they do not validate diarization or alignment. The app remains a research prototype with proposals separate from approved notes. Qualified clinical reviewers, physical hardware observations, institutional ownership, and receiving EHR validation remain external dependencies.

FHIR mapping source: [HL7 R4 DocumentReference](https://hl7.org/fhir/R4/documentreference.html). Export is a single DocumentReference, not a FHIR document Bundle, transaction, or conformance certification.
