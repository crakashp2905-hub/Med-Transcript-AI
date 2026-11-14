# Evidence-linked local consultation transcription and note review: engineering evaluation draft

**Manuscript status:** internal draft, not peer reviewed  
**Evidence class:** public mock/development data and software verification  
**Clinical validation:** none  
**Clinical release authorized:** no

## Abstract

We describe an English-only, local-first consultation documentation prototype that links timestamped transcript segments and typed clinical facts to source evidence, presents deterministic and optional local drafting proposals, verifies note/source consistency, and reserves approval and export for a clinician. We report a frozen public mock consultation ASR comparison as a development benchmark and specify a separate source-linked verification hypothesis. Across seven local text-only ASR configurations on 118 clips from 20 consultation groups (2,264 reference words), the lowest normalized word error rate (WER) was 8.70%; all seven configurations failed the unchanged 5% development gate. Seven additional candidates remained unranked because access, resource, or user-spending constraints prevented execution. These results do not establish clinical accuracy, timestamp validity, patient safety, clinician productivity, or efficacy. Independent clinical adjudication, formal related-work review, and planned verification ablations remain outstanding.

## 1. Motivation and intended use

Consultation documentation tools can introduce transcription errors, omit source statements, change negation or attribution, and create unsupported note claims. A reviewable system should preserve source audio and transcript provenance, make proposed facts traceable to evidence, surface uncertainty, and keep machine output distinct from clinician-approved documentation.

The prototype is intended for English outpatient documentation research under clinician supervision. It prepares audio, transcripts, evidence-linked facts, warnings, and note proposals. It does not independently diagnose, prescribe, sign a medical record, or write to an EHR. The interface requires clinician review and exact-version approval before export.

## 2. Related work and scope of claims

A systematic related-work search has not been completed for this draft. Relevant areas for a future review include clinical speech recognition, ambient documentation, evidence-grounded generation, source-to-note coverage, clinical negation and temporality, human factors, and early-stage evaluation of AI decision-support systems. No completeness or novelty claim is made. The source-linked BECCSV method is an engineering hypothesis, not a demonstrated new clinical method. This section must be completed with screened and cited literature before external scholarly submission.

## 3. System and method

### 3.1 Application workflow

An authenticated user creates a synthetic-only encounter and records processing permission. Audio is uploaded with declared size and SHA-256, sealed, and passed to an authorized local ASR worker. The worker appends an immutable timestamped transcript version. Fact proposals carry typed clinical fields and exact segment/character-span evidence. A deterministic note template is the baseline; optional model drafting remains a separate proposal. Independent deterministic verification produces findings and approval gates. A clinician may inspect audio and citations, edit the note, and approve an exact saved version. Export rechecks approval and source provenance.

The architecture and module contracts are documented in [`product-architecture.md`](../product-architecture.md). The application does not select a model based only on benchmark rank; inference profile admission is a separate decision.

### 3.2 Source-linked verification hypothesis

The in-house BECCSV hypothesis represents source facts, note claims, and typed evidence/consistency relations. It checks source-to-note coverage and note-to-source support, including polarity, subject, temporality, uncertainty, and medication relationships. Deterministic rules remain authoritative for approval; optional model judgments are advisory and cannot clear a gate. The complete hypothesis and synthetic protocol are in [`BECCSV-paper-draft-v0.1.md`](BECCSV-paper-draft-v0.1.md) and [`beccsv-protocol-v1.md`](beccsv-protocol-v1.md).

### 3.3 Data and evidence contracts

Source-linked facts require a valid transcript segment ID and exact quote offsets. Facts preserve assertion, subject, uncertainty, temporality, origin, review state, and typed relations. Transcript edits produce a new version; dependent evidence, verification, or approvals can become stale. Unavailable values remain unknown rather than being inferred. No generated proposal is a clinician-approved record.

## 4. Experimental setup

### 4.1 ASR development comparison

The published comparison is generated from locked public mock consultation manifests and frozen hypothesis reports. It includes 118 clips from 20 consultation groups and 2,264 reference words. Seven local model/runtime configurations use text-only adapters. The maximum normalized WER gate is 5%. Failure policy, model/runtime configuration, dataset and report hashes are retained in the generated [benchmark publication bundle](../../evaluation/publications/mta-17-03-benchmark-tables-v1.json) and [tables](../../evaluation/publications/mta-17-03-benchmark-tables-v1.md).

Text-only adapters do not prove that a model produces valid timestamps in application inference. The comparison is development evidence, not independent acceptance. Model rank does not itself change the configured application model.

### 4.2 Baselines and planned verification comparisons

The deterministic template is the note-drafting baseline. Optional local drafting or verification models are evaluated only as proposals. The planned BECCSV baselines include deterministic checks, prompt/model self-critique, and a combined deterministic-plus-model advisory policy. Planned graph ablations remove source coverage, temporal edges, relationship checks, uncertainty handling, deterministic rules, or the optional local verifier.

The BECCSV comparison and its six graph ablations have not been run. No completed paired clinical verification comparison or independent human reference standard is available. The plans are not results.

## 5. Results and negative findings

| Rank | Local configuration | Normalized WER | Failed clips | 5% gate |
|---:|---|---:|---:|---|
| 1 | Omi Med STT v1 | 8.70% | 0 | Fail |
| 2 | Parakeet TDT 0.6B v2 | 13.25% | 0 | Fail |
| 3 | Distil Whisper Large v3 | 15.72% | 0 | Fail |
| 4 | Faster Whisper Large v3 | 16.56% | 0 | Fail |
| 5 | Whisper Small | 18.07% | 0 | Fail |
| 6 | Faster Whisper Tiny.en | 22.31% | 0 | Fail |
| 7 | Multimed Whisper Small English | 42.05% | 0 | Fail |

No evaluated local configuration meets the 5% gate. The seven complete runs had no failed clips under the benchmark's execution failure policy; this does not mean the hypotheses were error-free or clinically safe. Seven candidates remain unranked: three access-gated models, two resource-blocked candidates, and two paid services disabled by the user's no-paid-calls instruction. Their outcomes are unavailable, not zero-error.

The BECCSV synthetic development suite has seven metamorphic cases: five passed expected transformation behavior and two semantics-preserving transformations produced false alarms. Those are small software-test observations, not clinical false-alarm rates. Full comparison and ablations remain incomplete.

## 6. Threats to validity and limitations

- Public mock audio and references do not establish performance on real patient consultations.
- Training-set overlap, speaker independence, and generalization to other sites/accent groups are not established.
- WER can conceal critical medication, dose, allergy, negation, omission, and attribution errors.
- Text-only benchmarks do not measure application timestamps, audio alignment, diarization, or end-to-end latency.
- Model comparisons do not establish clinical acceptance or justify automatic model promotion.
- The verification cases are synthetic/development fixtures; two semantics-preserving cases generated false alarms.
- No qualified independent reviewers, adjudicated acceptance cohort, patient outcomes, or clinician time study are available.
- Planned verification baselines/ablations and systematic related-work review have not been completed.
- Hosted candidates remain unrun due user restrictions, access gates, or resource constraints. Missing values are not imputed.

## 7. Reproducibility and data availability

The frozen manifests, licenses where declared, model/profile hashes, script hashes, and environment are catalogued in [`reproducibility-pack-v3.json`](../../evaluation/reproducibility-pack-v3.json). The pack reports absent license/digest fields explicitly. The benchmark publication command is `python -m services.publication_bundle`; it rebuilds tables from frozen reports and performs no inference. Original benchmark reports and failure evidence remain the source of truth.

## 8. Ethics and conclusion

This draft reports engineering and public mock development evidence only. It is not a clinical trial or efficacy result. Do not use it to support real-patient release, independent diagnosis/prescribing, or a claim of improved patient outcomes. A prospective clinician-supervised study requires qualified reviewers, a canonical reporting-checklist crosswalk, institution and privacy approvals, a frozen protocol, and independent adjudication before participant recruitment.

## Author checklist before external submission

- Complete and archive a systematic, reproducible related-work search.
- Reconcile every reported number to a frozen machine-readable source and exact commit.
- Complete or explicitly defer the BECCSV baselines and predeclared ablations.
- Obtain qualified independent review and appropriate governance before clinical claims.
- Keep all unavailable, failed, and negative results visible in the submitted supplement.
