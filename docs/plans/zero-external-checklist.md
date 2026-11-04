# Med-Transcript-AI — 10/10 Self-Contained Engineering Checklist

**Repository:** https://github.com/crakashp2905-hub/Med-Transcript-AI  
**Reviewed HEAD:** `c1afa1e70277af0942c389a37a2cfdf4096c9cc0` (2026-11-04)  
**Scope:** English-only, local-first, synthetic/public-mock, no paid/hosted API, no new real patient data, no new clinical reviewers, no consent/legal/account activation, no additional hardware, no newly obtained external datasets.  
**Intended executor:** human developer or coding agent (Codex), working from this repository and **already available** local environments, fixtures and provisioned model assets.

## What “10/10” can mean with no external inputs

A **10/10 self-contained engineering and research prototype** means: secure local-only behavior, complete synthetic workflow, reproducible experiments, proper provenance, no known unaddressed P0 failures, reproducible builds/tests, honest quality gates, and polished presentation. It **does not** mean 10/10 clinical accuracy, certified medical safety, live Google OAuth activation, real-patient compliance, scientifically independent clinical validation or 5% ASR WER. These require either measured model improvement or external clinical/operational evidence. **Never mark those as done using synthetic labels or simulated sign-offs.**

### Baselines to preserve (not targets to rewrite)

- Existing 118-clip Omi benchmark: **8.70%** normalized WER (selected short clips).
- Three complete mock consultations Omi: **13.05%** normalized WER.
- Frozen MedDistractAudio long-consultation screen: Omi native-empty wrapper **16.41% clean / 17.22% distracted** normalized WER; other models were worse in that configuration.
- Current 5% normalized WER gate remains **failed**; no model gets automatically promoted.
- Diarization baseline: **50.91%** speaker-duration-weighted DER in the earlier development setup, with an improved channel-based alternative requiring different hardware assumptions.
- On eight source-note preservation fixtures, deterministic **8/8**, Qwen 1.5B **3/8** (two failures), Qwen 7B **0/8** (eight failures). These are not clinical note-accuracy results.
- Latest reviewed engineering change introduces local/demo testable Google OIDC controls; real Google credentials/activation are **not part of this plan**.

### Scope / execution rules

1. **No external sign-offs:** Do not invent clinicians, reviewers, institutional partners, privacy approvals or clinical gold labels.
2. **No paid APIs or new accounts:** No Whisper API, hosted LLM, live Google sign-in, cloud GPU or paid subscription is required.
3. **No new data collection:** Use already committed licensed mock inputs, pre-existing cached local audio and programmatically generated synthetic cases. If a source asset is absent, do not download it silently; mark the dependent inference test `not_run` and keep the model-free route passing.
4. **No performance fabrication:** Do not lower the 5% WER threshold, alter frozen references, omit failures, exploit test leakage or call a simulated success “clinical accuracy.”
5. **Preserve current functionality:** Immutable approval history, consent/revocation fences, manual review and local deterministic drafting are foundational, not expendable shortcuts.
6. **Do not conflate levels of readiness:** Separate offline demo, engineering verification, research evidence and clinical release.
7. **A checkbox is complete only with evidence:** PR/commit reference, test name(s), benchmark/report artifact, before/after comparison, and known limitations.

## Exit gates (must all be measured; never assume)

| Gate | Self-contained acceptance criterion | Clinical implication |
|---|---|---|
| G0 — Reproducible baseline | Same existing report metrics recomputed from hashes and frozen runs | None |
| G1 — Offline reliability | Zero external calls in full synthetic flow; all tests and build green | Does not prove real-patient security |
| G2 — Clinical safety invariants | Zero unintended auto-approval under injected dose/negation/role/evidence mutations; all test cases accounted for | Synthetic-scope only |
| G3 — ASR honesty | All local outcomes, failed cases, timestamps, WER and latency reported exactly; no model selected unless predefined gate truly passes | WER alone insufficient for clinical use |
| G4 — Research reproducibility | Frozen experiments, ablations, hashes, source code, full negatives and confidence intervals | Not independent clinical research |
| G5 — UX/recovery | Synthetic source-to-approved export, crash/retry/revocation, keyboard and screen-size tests pass | Not a clinician usability study |
| G6 — Security simulation | Auth, tenant isolation, threat tests, secret scans, encryption/restore and tamper alarms pass in local test environment | External audit/keys still missing |
| G7 — Documentation integrity | API docs, README, diagrams and dashboards agree with current evidence | No regulatory claim |
| G8 — Clinical release | Must remain `BLOCKED_EXTERNAL_EVIDENCE_REQUIRED` without independent gold, clinician study, infra and approvals | Cannot be completed under this no-external-input mandate |

## Mandatory definition of done for every task

`[ ]` changes to `[x]` only after: (a) code exists; (b) positive/negative tests pass; (c) offline/model-free or cached-model execution is documented; (d) evidence artifact is hashed; (e) failures and limitations are disclosed; (f) README/docs updated where user-facing. Model-dependent tasks are **not** complete if weights are absent; use `blocked_missing_local_artifact`.

---

## 00. Integrity, scope and non-negotiable rules (P0; 12 tasks)

- [ ] **00-01** Record a baseline snapshot of branch, commit, environment, installed artifacts, tests, known failures, and benchmark hashes in `evaluation/reports/engineering-baseline.json`; verify every reported path exists.
- [ ] **00-02** Keep Version 1 English-only; remove non-English, MRI, X-ray and TTS work from critical-path milestones without deleting previously documented future plans.
- [ ] **00-03** Define a machine-readable release matrix: `offline_demo`, `engineering_verified`, `research_evidence_complete`, `clinical_approved`; prohibit collapsing the four into one `ready` boolean.
- [ ] **00-04** Make the current 5% normalized WER threshold immutable inside frozen benchmark contracts; new exploratory goals require new versioned protocols, never edits to old locks.
- [ ] **00-05** Ensure every model/report uses all predeclared cases with failure-inclusive denominators; failed samples count as full-reference deletions where specified.
- [ ] **00-06** Record the known benchmark baselines without mixing datasets: 8.70% short clips; 13.05% three long consultations; 16.41% clean / 17.22% distracted on MedDistractAudio.
- [ ] **00-07** Prevent test and demo fixtures from being mislabelled as clinical gold or independent human adjudication in exports, README, UI, dashboards and API schemas.
- [ ] **00-08** Define a `no_external_dependency` development profile that fails if an operation attempts hosted inference, downloads, telemetrics, live OAuth, or patient-data processing.
- [ ] **00-09** Add a provenance record for every derived artifact: source commit, dataset SHA, code SHA, model digest, config digest, date, status, limitations and validation scope.
- [ ] **00-10** Retain an immutable index of negative, failed, timed-out, interrupted and partial experiments; never overwrite them with repaired runs.
- [ ] **00-11** Specify a severity model (`P0`, `P1`, `P2`) and mark unsafe auto-approval, identity leakage, missing audit and corrupted evidence as release blockers.
- [ ] **00-12** Add a documented evidence hierarchy: independent clinical labels > non-independent source references > developer-authored synthetic gold > model judgments; the lower tier may not impersonate a higher one.

## 01. Repository architecture and maintainability (P0; 16 tasks)

- [ ] **01-01** Separate the 28 KB `services/api/main.py` into bounded routers by encounters, authorizations, audio, jobs, auth, transcript and exports; preserve existing endpoints and response contracts.
- [ ] **01-02** Split the 38 KB `services/review/routes.py` by extraction, draft editing, verification, approval, amendments and export, with a shared service layer and typed exceptions.
- [ ] **01-03** Refactor the approximately 48 KB `apps/clinician-web/src/main.tsx` into screens/hooks/API clients/stores without changing the existing clinician journey.
- [ ] **01-04** Introduce typed `ClinicalFact`, `TranscriptVersion`, `EvidenceSpan`, `ClaimRelation`, `VerificationFinding`, `NoteVersion`, `InferenceReceipt`, and `Approval` boundaries for all modules.
- [ ] **01-05** Use a single explicit state machine for encounter stages and transition guards; reject illegal, stale, double, revoked and cross-tenant transitions.
- [ ] **01-06** Replace loosely coupled `dict` payloads with Pydantic data contracts at persistence boundaries, retaining migration-compatible serialization.
- [ ] **01-07** Implement stable schema versions and `migrate(x -> x+1)` tests for transcript, note, model proposal, report and audit records.
- [ ] **01-08** Centralize deterministic hashing/canonical JSON; add golden cross-platform hash vectors for Unicode, decimals, nulls, sorted keys and line endings.
- [ ] **01-09** Ensure all ASR, diarization, extraction, drafting and verifier providers implement declared interfaces and surface provider-specific limitations.
- [ ] **01-10** Introduce typed non-sensitive error codes with stable client mappings; never return prompt, token, secret, audio or source text in error strings.
- [ ] **01-11** Consolidate configuration validation in startup checks and render a redacted config fingerprint to local diagnostics.
- [ ] **01-12** Apply strict import boundaries so evaluation tools cannot mutate production database state or promote models.
- [ ] **01-13** Enforce format/lint/type checks for Python and TypeScript in reproducible CI, including an explicit no-network test lane.
- [ ] **01-14** Add a small architecture-decision-log folder for scoring rules, provenance, safe defaults, local-only limits and compatibility choices.
- [ ] **01-15** Add branch-independent API contract snapshots and review every new endpoint for backwards compatibility.
- [ ] **01-16** Remove dead paths and duplicative experiment helpers only after snapshot-based reproduction of historical reports succeeds.

## 02. ASR-101: accuracy, text integrity and timestamps (P0; 20 tasks)

- [ ] **02-01** Build an error taxonomizer for substitution, deletion, insertion, silences, disfluency, boundary splits, uncertain references and overlap; export per-case diagnostics without editing the references.
- [ ] **02-02** Partition errors by patient/clinician reference roles, but explicitly mark that reference roles are not automatically predicted diarization.
- [ ] **02-03** Report WER/CER in both raw and normalized form and retain punctuation, units, numerals and drug spellings in clinical-term metrics.
- [ ] **02-04** Perform oracle-free, source-only chunk selection; compare 30-second fixed, pause-aware, overlap-aware and source-time-only strategies with all parameters frozen before scoring.
- [ ] **02-05** Study whether reference uncertainty/overlap accounts for measured errors without excluding those words from the primary frozen score.
- [ ] **02-06** Isolate native-empty outputs from actual decoder exceptions; allow empty speech only under a documented model-specific policy and preserve every missing word penalty.
- [ ] **02-07** Benchmark overlap stitching using audio-only alignment and deterministic text deduplication; reject accidentally dropped or duplicated words.
- [ ] **02-08** Add explicit start/end coverage accounting so every submitted audio sample is accounted for, including silence, incomplete inputs and failed windows.
- [ ] **02-09** Implement timestamp capability registry (`none`, `chunk`, `segment`, `word`) and prohibit a chunk bound being called a word timestamp.
- [ ] **02-10** Check timestamp monotonicity, duration bounds, gaps, drift, duplicates, repeated segments and hallucinations in long silence.
- [ ] **02-11** Add a robust transcription postprocessor that preserves uncertainty, negation, doses and source words; any correction suggestion must be separately recorded, never overwrite ASR raw output.
- [ ] **02-12** Make clinical terminology hints opt-in and scoped to a fixed, non-leaking local lexicon; measure both benefit and medication-name hallucination risk.
- [ ] **02-13** Benchmark model throughput and memory on existing hardware under controlled warm and cold runs; record CPU threads, RAM, runtime and inference queue wait.
- [ ] **02-14** Evaluate primary ASR on the existing short-clip, three-long and MedDistractAudio corpora separately; do not synthesize a single misleading universal WER.
- [ ] **02-15** Run all installed local ASR configurations with pinned artifacts and source hashes; preserve `unable_to_run` status where weights are absent.
- [ ] **02-16** Add adversarial synthetic audio for silence, clipping, repeated prompts, numerical doses, medical homophones and intentionally ambiguous utterances.
- [ ] **02-17** Add metamorphic tests: volume change, added leading/trailing silence, mild resampling and split/rejoin should not silently corrupt source integrity.
- [ ] **02-18** Develop a safe `retranscribe_span` tool that produces a candidate transcript version linked to old audio offsets and requires explicit review.
- [ ] **02-19** Compare keyword recovery from different ASR models without automatically merging unsupported medical terms; benchmark a candidate-selection policy before activating it.
- [ ] **02-20** Keep the unchanged 5% WER gate; if none passes, retain `ASR_NOT_ADMITTED` and the already working manual transcript fallback.

## 03. Speaker diarization and multichannel attribution (P0; 15 tasks)

- [ ] **03-01** Separate `speaker clustering`, `role identification` and `channel assignment` into independent result types, avoiding implicit clinician/patient mapping.
- [ ] **03-02** Make two-channel acquisition a first-class optional pathway when device inputs actually support it, with truthful per-channel hardware detection.
- [ ] **03-03** Add deterministic cross-talk, channel swap, empty channel, mono fake-stereo and desynchronization detectors.
- [ ] **03-04** Construct a robust channel-first baseline using the existing channel-separated recordings; compare its speaker-duration metrics with the single-mic VAD/embedding pipeline.
- [ ] **03-05** Reproduce and pin the current weighted DER baseline (~50.91%) rather than claiming the heuristic clustering is reliable.
- [ ] **03-06** Measure DER, missed speech, false alarm, confusion time, overlap errors and role-confirmation workload separately.
- [ ] **03-07** Implement minimum-turn duration, speaker-change boundary and false-split diagnostics; record high cluster counts as unresolved rather than normal.
- [ ] **03-08** Investigate deterministic clustering constraints only on development cases, including expected speaker count as a declared experimental assumption.
- [ ] **03-09** Use `unknown` for low-confidence source regions; block role-sensitive note claims until confirmed.
- [ ] **03-10** Detect overlapping speech explicitly or mark it unsupported; never assign overlapping assertions to one speaker by guess.
- [ ] **03-11** Test role reassignment after transcript corrections; downstream note evidence and approvals must become stale.
- [ ] **03-12** Create a synthetic turn-swapping suite to ensure semantic claims cannot switch from patient to clinician without warnings.
- [ ] **03-13** Optimize speaker review UI: play exemplar snippets, batch-confirm unambiguous turns, isolate ambiguous boundaries.
- [ ] **03-14** Expose a scorecard comparing single-channel, 2-channel and multi-input configurations without implying device equivalence.
- [ ] **03-15** Keep automatic diarization experimental until a predefined score and human-review policy are satisfied.

## 04. Structured clinical fact extraction (P0; 18 tasks)

- [ ] **04-01** Model each atomic fact as `subject + predicate + object + polarity + certainty + temporality + source_evidence`, optionally expanded for medication/dose/route/frequency.
- [ ] **04-02** Do not store a whole segment as a clinical fact when it contains distinct clauses; make all source character offsets exact.
- [ ] **04-03** Implement medication-to-dose and medication-to-frequency associations, including two drugs with different prescriptions in one sentence.
- [ ] **04-04** Support stopped, restarted, reduced, planned, historical and patient-reported medications without inventing current prescription status.
- [ ] **04-05** Distinguish family history from patient history, clinician speculation from diagnosis, patient denial from doctor question and plans from actions completed.
- [ ] **04-06** Preserve uncertain, hedged and questioned statements as uncertain; missing information must stay `unknown`.
- [ ] **04-07** Implement explicit negation scope for conjunctions, exceptions and multiple conditions; fallback to review rather than guessing.
- [ ] **04-08** Normalize units using safe exact decimal arithmetic and bounded conversion tables, preserving original surface string and source evidence.
- [ ] **04-09** Add drug dose value/unit/route/frequency/duration slots with confidence-by-validated-rule rather than unverifiable numeric model certainty.
- [ ] **04-10** Implement anatomy/laterality relations and robust tests for left/right swaps and different entities in one utterance.
- [ ] **04-11** Create an `evidence graph` mapping original audio -> transcript segment -> exact span -> atomic fact -> note statement -> export.
- [ ] **04-12** Build a source-coverage analyzer that distinguishes clinical omissions from irrelevant fillers; do not claim that word-span coverage proves clinical completeness.
- [ ] **04-13** Add duplicate-fact detection that retains contradictory or temporally distinct assertions instead of deleting apparent duplicates.
- [ ] **04-14** Support unrecognized terminology with explicit `unmapped` status rather than expanding a short fixed dictionary into fabricated certainty.
- [ ] **04-15** Run deterministic and installed local-Qwen extraction in shadow mode on the same frozen synthetic corpus, with an exact output/schema failure table.
- [ ] **04-16** Ensure the LLM cannot create fake segment IDs, span offsets or quotes; reject mismatches and preserve the rejected raw output only in redacted local developer diagnostics.
- [ ] **04-17** Add structured evaluation of fact precision/recall, entity-relation correctness and clinically important omissions against developer-authored synthetic scenarios only.
- [ ] **04-18** Require human review on incomplete models, cross-utterance pronouns, ambiguous medication attachment or unknown speaker attribution.

## 05. SOAP drafting, summarization and local LLM quality (P1; 14 tasks)

- [ ] **05-01** Keep deterministic reviewed-fact SOAP generation as the always-available baseline and offline fallback.
- [ ] **05-02** Formalize clinician-typed Objective vs reported Subjective facts; prevent invented examinations, vitals and assessments.
- [ ] **05-03** Make an LLM draft an unapprovable proposal, never an approval or source-transcript replacement.
- [ ] **05-04** Restrict drafting to cited reviewed fact IDs with a version hash and explicit bounded schema; fail closed on unknown IDs.
- [ ] **05-05** Compare Qwen 1.5B and 7B already installed with identical prompts, inputs, timeout budgets, model digests and full failure accounting.
- [ ] **05-06** Diagnose and publish the 8-case drafting result (8/8 deterministic, 3/8 Qwen 1.5B with 2 failures, 0/8 Qwen 7B with 8 failures) without hiding poor models.
- [ ] **05-07** Try smaller structured prompts, source-to-note subtask decomposition, grammar-constrained output and chunked fact sets only as separate ablations.
- [ ] **05-08** Measure note factuality, exact preservation, section correctness, length, duplication, omissions, unsafe claims, latency and timeout rate.
- [ ] **05-09** Add a configurable deterministic note-style layer, preserving the meaning and evidence of each assertion.
- [ ] **05-10** Ensure copied clinician-entered facts are visibly marked as clinician additions, not fabricated source citations.
- [ ] **05-11** Ensure every generated note statement exposes the underlying evidence and includes a source version watermark.
- [ ] **05-12** Block contradictions, unmapped critical fields, stale facts and incomplete source coverage before note approval, even if a local model claims success.
- [ ] **05-13** Prepare a locally runnable prompt-evaluation harness with frozen prompts and JSON-only reports; prohibit hidden modifications based on acceptance-only data.
- [ ] **05-14** Support `no LLM available` mode without degrading upload, transcription, manual editing, deterministic drafting or export.

## 06. Independent verification and safety invariants (P0; 20 tasks)

- [ ] **06-01** Write the claim-verification contract around supported / contradicted / insufficient-evidence / ambiguous, not unsupported free-text opinions.
- [ ] **06-02** Apply deterministic safety checks regardless of local-LLM verdict; model agreement cannot clear a hard clinical contradiction.
- [ ] **06-03** Expand relation tuples for medication-dose-route-frequency-duration-time, allergy-reaction, subject-diagnosis, anatomy-laterality and conditional instructions.
- [ ] **06-04** Make numbers, decimal points and units clinically typed; detect `5 mg` vs `0.5 mg`, `mg` vs `mcg`, and once vs twice daily.
- [ ] **06-05** Distinguish omitting a source symptom from compressing nonclinical conversational filler; document exact evaluation semantics.
- [ ] **06-06** Treat quoted instructions, malicious prompts, HTML, markup, and user utterances as untrusted data throughout model and verifier prompts.
- [ ] **06-07** Implement mutation generators for each fact tuple: one change at a time, then pairwise mutations, then temporal and coreference swaps.
- [ ] **06-08** Add metamorphic tests: safe paraphrase and exact unit-equivalent claims should stay admissible; critical reversals must require review.
- [ ] **06-09** Retain and reproduce the developer-authored 52-case retrospective result (13 -> 0 rule misses, four false alarms) without interpreting it as clinical sensitivity.
- [ ] **06-10** Report per-class TP, FP, FN, TN plus abstentions, timeouts, malformed output and incomplete checking.
- [ ] **06-11** Run ablations: basic lexical rules; relational rules; local verifier alone; rules + local verifier; and deterministic source-only baseline.
- [ ] **06-12** Introduce a second local verifier only if its distinct errors measurably improve a fixed combined policy; otherwise remove redundant compute.
- [ ] **06-13** Ensure verification is complete over all note facts, not just up to 20 selected claims; use bounded batches and merge with exact coverage accounting.
- [ ] **06-14** Reject silent batch omissions, duplicated IDs, invented quote evidence, unsupported role reassignment, and stale verification.
- [ ] **06-15** Guarantee a semantic verifier timeout does not convert a blocking note into an approvable note.
- [ ] **06-16** Generate an explanation for each critical warning with source quote, alleged mismatch, fields and validator version; avoid invented rationales.
- [ ] **06-17** Add adversarial replay testing of old approved note versions after source correction and after a new model version is installed.
- [ ] **06-18** Build a tamper test suite: alter source byte, segment quote, hash, fact, report and approval, then demonstrate rejection at the appropriate boundary.
- [ ] **06-19** Add formal state/invariant assertions: approval requires current source, completed review, no blocking findings and exact verification hashes.
- [ ] **06-20** Maintain a documented non-bypassable manual-review path for contradictions and disputed source words.

## 07. Audio capture, uploads, worker and crash safety (P0; 16 tasks)

- [ ] **07-01** Verify 30-minute browser recorder storage and playback for 1, 2, 4 and 8 channels using generated synthetic signals and bounded disk usage.
- [ ] **07-02** Run resume/upload interruption at each transition: capture, IndexedDB commit, server chunk ACK, finalize, ingest and ASR publication.
- [ ] **07-03** Ensure duplicate/idempotent uploads produce one stable asset hash and no extra job or partial publish.
- [ ] **07-04** Test lost last chunk, truncated chunks, random chunk order, wrong offset, oversized request and digest mismatch.
- [ ] **07-05** Add deterministic media format tests for WAV, MP3/M4A/WebM/Ogg where local codecs exist; unsupported codecs must fail safely.
- [ ] **07-06** Test browser quota exhaustion, storage eviction and microphone removal without claiming the recording was successfully retained.
- [ ] **07-07** Keep provisional previews separate from final transcript revisions; no preview segment may be approved.
- [ ] **07-08** Add a durable queue dashboard with per-stage state, attempts, lease owner, timeout and consent/revocation state.
- [ ] **07-09** Test worker crash and recovery at every transaction boundary, including stale lease and resumed channel checkpoints.
- [ ] **07-10** Prevent two processes from processing the same heavyweight model slot, with a bounded worker lock and informative queue status.
- [ ] **07-11** Retest the eight-channel 20/30-minute synthetic duration stress scenario; distinguish transport throughput from transcription accuracy.
- [ ] **07-12** Track exact original/normalized/isolated audio hashes so cross-channel confusion cannot corrupt source lineage.
- [ ] **07-13** Audit live server recording prefixes for safe expiry, recovery authorization, retained copies, and deletion after user discard.
- [ ] **07-14** Test consent revocation during capture, upload, audio normalization, diarization, ASR, drafting and verification; publication must be blocked.
- [ ] **07-15** Add a model-memory pressure probe that fails or queues before OOM while leaving completed source state intact.
- [ ] **07-16** Introduce deterministic fault injection for slow disks, write failures, process kills, database busy errors and absent models.

## 08. Clinician experience and inspection features (P1; 14 tasks)

- [ ] **08-01** Provide a single encounter workspace with audio, source transcript, reviewed facts, SOAP note, warnings and evidence links in synchronized panes.
- [ ] **08-02** Ensure clicking any note claim seeks to the correct source audio/segment and never pretends chunk bounds are aligned word timestamps.
- [ ] **08-03** Make speaker-identity uncertainty visible and offer source-linked bulk role correction with diff preview.
- [ ] **08-04** Add keyboard-first workflows, accessibility labels, consistent focus, screen-reader status and responsive layout.
- [ ] **08-05** Show source-completeness status, unverified segments, uncertain doses and pending reviewer decisions before drafting.
- [ ] **08-06** Display generated-vs-deterministic note side-by-side and highlight changed meanings, omissions and extra claims.
- [ ] **08-07** Make every correction create an auditable immutable version; never silently alter an approved record.
- [ ] **08-08** Make warnings severity ordered but not auto-dismissable when clinical-critical, and show exactly which fact blocks approval.
- [ ] **08-09** Treat plain-language patient summary as a separately reviewed draft with explicit non-delivery status.
- [ ] **08-10** Preserve source attribution and version history in FHIR DocumentReference exports; label recipient-specific EHR conformance as untested.
- [ ] **08-11** Add first-run onboarding using only a prebuilt synthetic example, without asking for Google or external accounts.
- [ ] **08-12** Provide a user-facing troubleshooting guide for no local model, no microphone, full disk, expired session, codec problem and failed job.
- [ ] **08-13** Add Playwright test flows for recovery, source edits, errors, keyboard-only review, role correction and local-demo walkthrough.
- [ ] **08-14** Run visual regression snapshots at desktop/tablet/mobile resolutions using generated synthetic data only.

## 09. Evaluation design and scientific reproducibility (P0; 20 tasks)

- [ ] **09-01** Keep the 118-clip, 3-consultation and 8-foreground/16-condition datasets separately pinned; never claim mutually independent subjects from the paired clean/distracted samples.
- [ ] **09-02** Add a canonical data ledger recording source licenses, dataset hashes, group splits, background donor identity and transformation functions.
- [ ] **09-03** Verify exact reference and hypothesis hashes before and after every reported metric computation.
- [ ] **09-04** Produce machine-generated model cards including language, hardware, decoding settings, failures, timeouts, WER, role metrics and limitations.
- [ ] **09-05** Publish a full confusion/error spreadsheet-like CSV without PHI and without omitting failed examples.
- [ ] **09-06** Build paired-case comparisons with bootstrap over consultations rather than treating thousands of tokens as independent samples.
- [ ] **09-07** Add a `primary endpoint` registry freezing one ASR, one verification and one UX metric per experiment before evaluation.
- [ ] **09-08** Use the reserved acceptance data only for existing provenance/packet preparation; do not score models or tune rules on it without external adjudication.
- [ ] **09-09** Create explicit synthetic test suites with programmatic deterministic oracles for negation, medication swaps, dosage, roles and timestamps.
- [ ] **09-10** Run novel synthetic tests separately from upstream human transcripts; never merge synthetic success into clinically valid performance estimates.
- [ ] **09-11** Implement pairwise regression checks to reject parameter changes that regress critical-safety synthetic tests even when aggregate WER improves.
- [ ] **09-12** Maintain exact provenance of full and partial benchmark runs with retry ancestry and per-case completion data.
- [ ] **09-13** Enforce bounds/consistency checks for all benchmark arithmetic: numerator, denominator, percentage, zero cases, timeouts, hash mismatch.
- [ ] **09-14** Add model-independent reference quality diagnostics for uncertain labels, overlapping speakers, truncated transcripts and missing annotations.
- [ ] **09-15** Create a model/experiment comparison view that discloses task, dataset and evaluation scopes, avoiding cross-dataset ranking errors.
- [ ] **09-16** Re-run saved benchmarks through a read-only scorer from committed reports; verify scores match without model weights.
- [ ] **09-17** Label every claimed method novelty as `hypothesis` until there is a distinct algorithm with an ablation improvement over a fair baseline.
- [ ] **09-18** Generate a reproducibility bundle of model-free commands, artifact hashes, environment manifests and full negative results.
- [ ] **09-19** Require `independent_clinical_gold=false` and `clinical_release=false` in all developer-only reports until genuinely changed by external evidence.
- [ ] **09-20** Predefine what constitutes an inconclusive experiment and stop adding variants that cannot be evaluated under the resource budget.

## 10. Testing, quality gates and CI (P0; 14 tasks)

- [ ] **10-01** Fix or triage the November 2 `pip-audit --strict` failure; if an advisory exists, update dependencies using tested constraints, and preserve evidence of the outcome.
- [ ] **10-02** Confirm the latest November 4 main-branch CI passes before claiming its Google authentication changes were validated on hosted runners.
- [ ] **10-03** Add dedicated test lanes for unit, integration, PostgreSQL, browser, property/fuzz, security and offline model-free simulation.
- [ ] **10-04** Make CI fail if a model or benchmark attempts network access under `MED_TRANSCRIPT_OFFLINE=1`.
- [ ] **10-05** Test the OIDC flow with simulated, locally signed tokens (signature, audience, nonce, issuer, state replay and expiry) and no Google registration.
- [ ] **10-06** Run generated-workload tests for race conditions, replay keys, cross-tenant isolation, stale ETags and concurrent approvals.
- [ ] **10-07** Add mutation tests around critical safety guards and prove tests detect deliberately injected bypasses.
- [ ] **10-08** Add randomized property-based tests for time windows, source spans, unit conversion and approval-state invariants using fixed seeds.
- [ ] **10-09** Measure and publish per-module coverage, but gate critical state/auth/security paths by mutation/behavior tests rather than only line coverage.
- [ ] **10-10** Make Windows and Linux test setup deterministic; record any permitted platform-specific divergence explicitly.
- [ ] **10-11** Run full frontend typechecking, build, audit and Playwright suites with synthetic fixtures and no backend cloud dependencies.
- [ ] **10-12** Add a daily offline release-readiness runner that reports `not established` rather than passing missing clinical requirements.
- [ ] **10-13** Make all test artifacts emit machine-readable JSON plus an accessible human-readable summary with failures at the top.
- [ ] **10-14** Fail the release build on any migration error, evidence mismatch, unsupported schema, stale approval or incomplete critical verification.

## 11. Security, privacy and adversarial hardening (P0; 20 tasks)

- [ ] **11-01** Write a data-flow threat model covering browser audio, IndexedDB, resumable server prefixes, worker temp files, prompts, model outputs, notes, exports, audit and backups.
- [ ] **11-02** Test source-level cross-tenant and cross-role access across every route, including historical notes and generated proposal IDs.
- [ ] **11-03** Verify session-cookie security, CSRF, state/nonce/PKCE, invited-account membership, subject pinning and revocation under local simulated OIDC.
- [ ] **11-04** Ensure every API route has an explicit authorization policy and test method/status variants, including routes mounted by new routers.
- [ ] **11-05** Avoid logging full note text, transcript snippets, secrets, auth cookies, API keys, audio data, prompts and provider responses.
- [ ] **11-06** Implement a local, no-secret leak scanner for Git-tracked files, generated reports, sample env files and fixture artifacts.
- [ ] **11-07** Reject SSRF via provider endpoints and redirects; block private/non-loopback destinations in offline mode, including DNS rebinding where applicable.
- [ ] **11-08** Constrain inputs, audio duration, JSON depth, request sizes, decompression, timestamps and expensive processing stages.
- [ ] **11-09** Run adversarial transcript prompt-injection cases; source utterances must never control application instructions, file access or note approval.
- [ ] **11-10** Protect against model output parser bombs, duplicate JSON keys, Unicode confusables, excessive facts, nested arrays and malformed schema.
- [ ] **11-11** Ensure evidence spans cannot point outside source transcript, outside tenant/encounter or into a different transcript version.
- [ ] **11-12** Prohibit silent hosted inference, automatic model downloads or telemetry in the offline demo; create network-denial test harnesses.
- [ ] **11-13** Build local encryption test paths for persisted files/backups using synthetic keys; explicitly document missing real key custody.
- [ ] **11-14** Verify restore, retention expiry, purge, legal hold and deletion across new auth tables, live audio prefixes, drafts and model-proposal records.
- [ ] **11-15** Add local tamper-evident audit chain verification and test detection of removed/reordered/mutated records; do not claim external immutability.
- [ ] **11-16** Generate SBOMs and pin hash-verified dependencies where tooling exists; offline audit must distinguish stale advisories from proved clean status.
- [ ] **11-17** Run container security checks: non-root, read-only rootfs, no unnecessary capabilities, private DB, bounded memory, no exposed default credentials.
- [ ] **11-18** Verify defense-in-depth for exported markdown/HTML/JSON/FHIR content, including escaping, formula injection in CSV-like exports and filename safety.
- [ ] **11-19** Test timing and behavior after consent withdrawal mid-inference; discarded outputs must not reappear via cache/retry.
- [ ] **11-20** Make the README prominently state synthetic/mock-only until independent patient-data authorization exists.

## 12. Performance and resource optimization on existing hardware (P1; 12 tasks)

- [ ] **12-01** Set a documented single-device CPU/16 GB RAM reference profile; avoid assuming an NVIDIA GPU or cloud account.
- [ ] **12-02** Collect stage-level latency: recording, transfer, normalization, ASR, diarization, extraction, drafting, verification, clinician review, export.
- [ ] **12-03** Measure cold and warm model initialization separately and quantify memory footprint and cache effectiveness.
- [ ] **12-04** Benchmark CPU thread settings and quantized local model runtime configurations only when model artifacts are already present.
- [ ] **12-05** Detect and prevent oversubscription when local ASR and Qwen model requests compete for memory.
- [ ] **12-06** Use bounded queues and explicit rejection/deferral under overload rather than OOM or silently unbounded wait.
- [ ] **12-07** Evaluate context truncation and note batch size effects on omissions and hallucinations, not only speed.
- [ ] **12-08** Add streaming file hashing/processing to avoid loading entire 30-minute multichannel recordings into memory.
- [ ] **12-09** Test database indexes and bounded list pagination for 1000 synthetic encounters, many note versions and multiple users.
- [ ] **12-10** Build resource-limit stress tests with fixed synthetic data seeds, repeatable durations and teardown guarantees.
- [ ] **12-11** Calculate successful-consultation local cost from measured CPU-seconds, memory/disk and a user-configurable electricity assumption, without inventing live prices.
- [ ] **12-12** Define latency targets for each local development device class; measure and report failures rather than disguising them as fast successes.

## 13. Fully offline reproducibility and packaging (P1; 12 tasks)

- [ ] **13-01** Provide `scripts/offline_preflight` that reports cached Python wheels, npm dependencies, model directories, codec availability and exact hashes before any build.
- [ ] **13-02** Provide a one-command offline model-free demo with bundled synthetic fixtures and no accounts, downloads or API calls.
- [ ] **13-03** Build a reproducible offline wheelhouse/npm cache bundle from existing local installation *if present*; mark missing caches honestly.
- [ ] **13-04** Use deterministic fake ASR, diarization, extraction and verifier adapters for smoke paths that must pass without installed weights.
- [ ] **13-05** Implement model-presence checks that produce `unavailable` rather than auto-installing/downloading a model.
- [ ] **13-06** Provide a Linux Docker Compose demo and Windows PowerShell local demo with isolated demo storage and cleanup.
- [ ] **13-07** Pin Python, Node, TypeScript, PostgreSQL, runtime and package versions and document tested minimum/maximum versions.
- [ ] **13-08** Create a repeatability command that rebuilds published metrics solely from committed hypotheses and manifests, without inference.
- [ ] **13-09** Ensure test fixtures do not contain real patient identifiers, live auth credentials or secrets.
- [ ] **13-10** Add disaster-recovery instructions for synthetic demo database, app config, encrypted backup drill and deleted-asset reconciliation.
- [ ] **13-11** Create an offline acceptance script: preflight -> tests -> mock full workflow -> metrics replay -> safety gates -> report.
- [ ] **13-12** Test the actual packaged artifact on a clean isolated local environment, with cached dependencies only; report if unavailable.

## 14. Research contribution: measurable, local-only novelty (P1; 12 tasks)

- [ ] **14-01** Select one narrow algorithmic contribution: e.g., uncertainty-aware source/evidence coverage and clinical-relation checking over deterministic and LLM baselines.
- [ ] **14-02** Specify the method mathematically: evidence graph, typed claims, relation signatures, contradiction and omission costs, abstention policy.
- [ ] **14-03** Implement the proposed method behind a feature flag; baseline behavior stays frozen and reproducible.
- [ ] **14-04** Use existing predeclared development data for optimization, and developer-authored synthetic adversarial oracles for reproducibility.
- [ ] **14-05** Compare at least four methods on identical cases: lexical rules, relation rules, LLM-only verdict, combined evidence-graph method.
- [ ] **14-06** Ablate each novel component: relations, negation scope, temporality, evidence coverage, model opinion and confidence/abstention.
- [ ] **14-07** Measure critical-error misses, benign false blocks, coverage, runtime, memory and reviewer-like correction events in simulated workflows.
- [ ] **14-08** Add perturbation stress tests with controlled surface paraphrases, speaker swaps, omitted clauses, reversed temporal qualifiers and misleading instructions.
- [ ] **14-09** Report uncertainty via exact denominators and case-level paired intervals; treat small synthetic data as mechanistic evidence only.
- [ ] **14-10** Document negative results where the novel method is slower or less accurate; do not modify reserved acceptance materials.
- [ ] **14-11** Prepare paper-ready method, experimental protocol, limitations, failure taxonomy and reproducibility appendices.
- [ ] **14-12** Do not claim an independently novel or clinically effective method without external comparison/review; use `candidate contribution` language.

## 15. Local product and investor demo excellence (P2; 12 tasks)

- [ ] **15-01** Ship a five-minute local walkthrough from synthetic consultation upload through review, blocked claim, correction, exact approval and export.
- [ ] **15-02** Record an audit-friendly demo scenario in which the model makes a deliberate drug-dose error and the deterministic gate blocks it.
- [ ] **15-03** Show a second scenario of legitimate paraphrase and avoid implying all paraphrases are unsafe by construction.
- [ ] **15-04** Add a local read-only showcase account/session simulator without Google registration; never call it verified live OIDC.
- [ ] **15-05** Offer a study dashboard comparing datasets and model variants with visible failures, no invented cost/accuracy, and model-not-admitted banners.
- [ ] **15-06** Generate screenshots and demo transcript using only locally available browser tooling and synthetic content.
- [ ] **15-07** Publish architecture diagrams, API examples, data lifecycle, threat model, model cards and limitations in version-controlled docs.
- [ ] **15-08** Document model license attribution and ensure redistributed fixtures and weights follow their actual licenses; do not distribute weight files by default.
- [ ] **15-09** Remove outdated README claims and stale metrics; make documentation links resolve and lead users to current frozen reports.
- [ ] **15-10** Build a 1-command status command that reports test pass/fail, offline mode, model availability, source hashes and clinical release blocked.
- [ ] **15-11** Provide a deployment simulation using the production Compose config with fake secrets and local TLS/proxy tests where cached tooling supports it.
- [ ] **15-12** Add a concise roadmap separating next offline engineering release, independent clinical acceptance, and future optional imaging/TTS work.

---

## Execution order for Codex (do not parallelize heavy local models on the 16 GB reference PC)

**Stage A — Stop release risk:** Sections 00, 01, 10 and the P0 security tasks of 11. Build the offline preflight and evidence inventory. Establish a clean baseline, investigate the dependency audit failure, then make basic CI and local synthetic flow green.

**Stage B — Clinical safety core:** Sections 04 and 06. Fully automate deterministic adversarial and metamorphic tests and strengthen atomic clinical fact/relationship coverage. Preserve clinician approval invariants.

**Stage C — Better real-audio handling:** Sections 02, 03 and 07. Use exact existing datasets and already provisioned models. Report any ASR/diarization failures honestly; keep model admission blocked if the 5% gate is unmet.

**Stage D — Polished assistive workflow:** Sections 05 and 08. Keep deterministic drafting as the primary accurate-preservation mode until LLM proposals beat it on prespecified tests.

**Stage E — Research and demo:** Sections 09, 12, 13, 14 and 15. Rebuild all metrics, packaging, research ablations, model-free showcase and status reports.

### Suggested local commands (only where dependencies are already installed)

```powershell
# From repository root. No new accounts or paid APIs.
python -m pytest -q
cd apps/clinician-web
npm run build
cd ../..
python -m services.release_readiness --out data/offline-release-evidence.json --check-release
# A non-zero release-check result is EXPECTED: clinical approval remains blocked.
```

Do not run installation/download commands without explicit package-cache and offline checks. Use new output paths; preserve old locked artifacts. Build a dedicated `python -m services.offline_acceptance` command that runs all locally executable checks and produces `data/offline-acceptance-summary.json` plus `docs/offline-acceptance-summary.md`.

## Final score rubric — engineering-only

| Dimension | Weight | 10/10 condition inside this scope |
|---|---:|---|
| Architecture/maintainability | 15 | Typed services, backward compatibility, manageable modules |
| Reliability and recovery | 15 | All synthetic crash/retry/revocation paths tested |
| Safety by design | 20 | Zero missed *predefined synthetic invariant* violations, fail-closed approvals |
| Research/evaluation integrity | 20 | Exact reproducibility, fair baselines, full failures, never claims clinical gold |
| Security and privacy simulations | 15 | Offline auth, isolation, tamper/backup tests; no outbound network |
| UX and reproducibility | 10 | One-command offline synthetic workflow, robust inspector UI |
| Documentation and product clarity | 5 | Accurate claims, current report links, limitations and model licenses |
| **Total** | **100** | **100/100 engineering-prototype points is a target, not a guaranteed outcome** |

The true clinical/product/novelty ratings are scored separately. **Completing every developer-only task never, by itself, turns clinical deployment readiness into 10/10.** It creates a technically defensible foundation for later independent studies.

## Copy-paste execution brief for Codex

> You are upgrading the checked-out `Med-Transcript-AI` repository as an **English-only, entirely local, synthetic/public-mock medical documentation research prototype**. Follow the 247 checkboxes above in priority order, with P0 before P1 and P2. You must not ask for a paid API, Google OAuth account, hosting, GPU purchase, new clinical dataset, doctor, hospital, real patient, external approval or model-weight download. Work only with already present code, frozen reports, permitted locally cached dependencies and present model assets. If an artifact is missing, produce an accurate `blocked_missing_local_artifact` entry and test a deterministic fallback instead. Do not create fake human reviewer attestations. Do not mark clinical admission, paper novelty or the 5% WER threshold as achieved without genuinely measured evidence. Maintain the exact-version review/approval safeguards and always test consent revocation, stale sources, source attribution, critical medication and negation changes, and tenant isolation. Before modifying code, run and record the current baseline. Implement one verifiable vertical slice at a time, adding both positive and negative tests and linking evidence of completion. After each slice, rerun the appropriate tests, preserve failed experiments, update docs, and produce a machine-readable status report with `implemented`, `verified`, `failed`, `blocked_external_evidence`, `blocked_missing_local_artifact` or `not_started` per task. Produce a final offline acceptance report and explicitly retain `real_patient_release_authorized=false`. Never misrepresent synthetic evidence as clinical ground truth. Quality is judged on reproducibility, engineering correctness, safety invariants and honest reporting—not on the number of checked boxes.

### Required output artifacts from implementation

- `docs/engineering-scorecard.md` — every task ID, status, evidence references, regressions and next actions.
- `evaluation/reports/offline-acceptance-<version>.json` — hashes, test results, timing and safety gates.
- `docs/architecture-decisions/` — new architecture/clinical-safety decisions, including why alternatives were rejected.
- `docs/benchmark-integrity.md` — frozen datasets, models, hashes, denominator/failure accounting and negative findings.
- `docs/demo-runbook-offline.md` — one-command synthetic walkthrough, requirements, known gaps and troubleshooting.
- `docs/remaining-external-evidence.md` — human/clinical/legal/security obligations explicitly outside current scope; do not claim these were completed.
