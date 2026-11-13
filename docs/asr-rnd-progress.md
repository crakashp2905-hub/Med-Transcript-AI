# In-house ASR R&D progress

This progress record tracks work against the 95-item in-house ASR addendum. The
addendum's benchmark and admission claims remain unchanged. Code and synthetic
tests do not establish ASR accuracy, clinical validity, or external acceptance.

## Completed engineering tasks

| Task | Result | Evidence | Limits |
|---|---|---|---|
| MTA-ASR-A01 | Verified the historical WER baselines as four distinct scopes; no aggregate cross-cohort ranking. | `scope-separated-baselines-v1.json` SHA-256 `c9b84529a7b27c6e85d0c8857b0091b6`; denominators are 197/2,264 short clips, 679/5,204 three consultations, 2,245/13,683 clean, and 2,356/13,683 distracted. `tests/test_baseline_summary.py`: 2 passed; its replay verifies pinned source digests. | Historical benchmark replay only; all four configurations fail the unchanged 5% gate. |
| MTA-ASR-A02 | Added a strict offline evaluation contract binding rights-reviewed manifests, recording hashes, consultation groups, channel observations/maps, reference digests, local model revision, decoder settings, normalization, and failure-inclusive denominators. | `services/asr/evaluation_contract.py` is enforced by `services/evaluation.py` before inference and before writing the report. Contract tests cover the three existing public sample manifests, malformed-manifest rejection before model invocation, contract digest tampering, and a failed sample retained in the reference denominator. `tests/test_asr_evaluation_contract.py` plus `tests/test_evaluation.py`: 22 passed. | Uses the current sample-based local faster-whisper evaluation adapter. It does not validate full-consultation reports or establish model accuracy. |
| MTA-ASR-A03 | Replayed word-level edit alignments for the three frozen full-consultation baseline groups; per-case substitutions, deletions, and insertions reconcile to the published aggregate. | `tests/test_asr_word_error_replay.py`: 1 passed. Frozen baseline SHA-256 `d3cd848d0179ad3159cb999c4e8812ffa65dd57646ca5dea8b0c64692895c1ce`; diagnostics SHA-256 `b7d30f4249c103b43a0d8f896c1edf0bdb06213e2a4c1cf83a9979626b908a40`. Replayed total: 679 edits / 5,204 words. | Reference-turn attribution is lexical diagnostics, not word timestamp alignment or clinical adjudication. |
| MTA-ASR-A07 | Added versioned reference uncertainty handling. Optional flagged/not-flagged sensitivity strata leave primary WER and all hard reference words intact; the policy ID and digest enter the evaluation contract, and reports are write-once. | `tests/test_asr_evaluation_contract.py` and `tests/test_evaluation.py`: 23 passed. Synthetic flagged sample preserves the five-word primary denominator across policies while producing a different contract digest. | Only explicit sample-level `reference_uncertain` flags are consumed; this adds no adjudicated gold labels or clinical validation. |
| MTA-ASR-A08 | Built a read-only interactive local review packet with exact source clip playback, frozen reference, all candidate alternatives, source interval and audio/model/profile/artifact digests. | `evaluation/reports/asr-error-review-v1.html`: 114 error-bearing clips across 8 frozen candidates; all 118 source audio hashes and run/reference joins validate. `tests/test_asr_error_review.py`: 2 passed; HTML parser and Node JavaScript syntax check pass. | Licensed public development utterances only; no human clinical review or adjudication is implied. The packet cannot edit references. |
| MTA-ASR-A09 | Froze secondary exact-concept endpoint definitions and added an impact-weighted concept error metric that requires a complete external weight mapping, binds its digest, and leaves primary WER unchanged. | `evaluation/clinical-asr-secondary-endpoints-v1.json`; `services/clinical_metrics.py`; `tests/test_clinical_weighted_metrics.py`, `test_clinical_metrics_report.py`: 6 passed. Synthetic tests cover weighted omissions/insertions, failed cases, missing weights, unchanged primary WER, and separate case/punctuation diagnostics. | Status: partial. No independently adjudicated concept or impact-weight data is bundled, so no real clinical weighted score was generated. Synthetic fixtures are not clinical gold. |
| MTA-ASR-A10 | Added paired foreground-cluster bootstrap intervals for distracted-minus-clean micro-WER, resampling both conditions together and retaining failed arms. | `evaluation/reports/paired-asr-bootstrap-v1.json`: 9 candidates, 8 paired foregrounds each, 10,000 iterations, deterministic seed; source pair IDs and failed statuses retained. Point estimates reconcile exactly with the frozen detailed ranking, including one failed pair. `tests/test_paired_asr_bootstrap.py` and `tests/test_paired_bootstrap.py`: 4 passed. | Eight convenience-sampled development consultations do not support clinical acceptance confidence claims; the 5% WER gate is unchanged. |
| MTA-ASR-B04 | Added a source-preserving candidate boundary: disabled enhancement returns the exact original path and digest; enabled transforms run on a byte-verified temporary snapshot and publish only a new, parent-linked candidate. | `tests/test_audio_enhancement.py`: 5 passed. Tests compare original bytes, validate parent receipts, prove a failing/mutating transform cannot change the source, and check transform frame preservation. Ruff and format checks pass. | This boundary alone does not claim audio or ASR improvement. |
| MTA-ASR-B06 | Added deterministic PCM quality diagnostics for clipping fraction, silence duration, per-channel RMS/imbalance, sample-jump indicators and optional span-labeled SNR. | `tests/test_audio_quality.py`: 4 passed using synthetic silence, clipping, stereo level imbalance, sample jumps and controlled speech/noise spans. Reports bind the audio hash and profile version; unlabeled SNR is explicitly `not_measured`. | Sample jumps are a discontinuity heuristic, and SNR is only estimated from caller-labeled synthetic spans. No real recording quality report or clinical interpretation is claimed. |
| MTA-ASR-B07 | Added versioned clean/degraded quality routing from measured clipping, silence, channel imbalance, sample-jump rate and explicitly labeled SNR flags. Routes are named candidates, carry reasons, emit no confidence, and always require full source audio and content. | `tests/test_audio_router.py`: 4 passed. Synthetic adverse signals route to review; tests prove every source sample ID and reference-word denominator remain unchanged and reject plans that omit cases. | Thresholds are deterministic heuristics, not calibrated probabilities. No real noisy-versus-clean routing performance has been measured. |
| MTA-ASR-B08 | Reconciled existing controlled channel-tone diagnostics and two-channel extraction/transcription path. The audit reports expected-versus-observed channel mapping and relative bleed-through; output keeps physical channel IDs while role/speaker identity remains explicitly unverified. | `tests/test_channel_signal_audit.py` covers correctly mapped signals, swapped channels, and injected bleed-through. `services/asr/channels.py` preserves exact channel extraction lineage and marks each segment `channel_is_not_verified_speaker`; combined output requires channel-role confirmation and cross-talk review. | Synthetic calibration signals establish mechanism only. No physical microphone capture, source identity, or clinical speaker accuracy has been validated. |
| MTA-ASR-B10 | Added and ran a local resource benchmark for RMS normalization, high-pass filtering, and spectral gating. | `evaluation/reports/audio-filter-resource-v1.json` SHA-256 `44a1f66c0fb861e9bb2ea191c0c03484ac3f2a202c6ae5adc564c8ba78c1e0d5`; 18 transform/clip measurements on Windows 11, Intel CPU, 8 logical CPUs. Longest available clip: 10.426 s; maximum observed CPU 1.906 s, wall RTF 0.630, CPU RTF 0.396, sampled process RSS 114,143,232 bytes. | Partial: only six short public development clips were available; this is not a worst-case duration or application memory admission result. RSS was sampled every 5 ms, process-wide, and excludes ASR model memory. |
| MTA-ASR-B05 | Evaluated RMS level normalization, 80 Hz high-pass filtering and spectral gating as separate candidates against unmodified audio using the same pinned local Omi decoder. | `evaluation/reports/audio-enhancement-paired-v2.json` SHA-256 `91a6e233141839aeeb70ce7ea8e0f970d5d452bf5feaa5919c293da36a387df4`; 6 paired clips × 4 arms, 0 failures, 134 reference words per arm. Each arm had 9 edits (6.716% WER); all 18 transformed paired cases were unchanged (0 improved, 0 degraded). Model and source-code hashes plus all candidate audio receipts validate. The unchanged <=5% gate fails for every arm. | One convenience-selected consultation with upstream, non-adjudicated mock references; no clinical benefit or production routing is established. |
| MTA-ASR-F01 | Implemented deterministic span risk records in `services/asr/risk_selector.py`; every signal now requires a method version and evidence SHA-256. | `tests/test_asr_risk_selector.py`: 9 passed; Ruff check and format pass. | Mechanistic unit evidence only. Upstream diagnostic producers are not yet wired into the selector; it does not measure audio or infer calibrated confidence. |
| MTA-ASR-F02 | Existing durable selective retranscription workflow verified: authenticated request, bounded crop, worker decode, immutable candidate result. | `tests/test_retranscription_workflow.py`: 3 passed, including actual WAV crop and source-version preservation with a fake local adapter. | No model accuracy claim; the integration fixture uses synthetic audio and a stub recognizer. |
| MTA-ASR-F03 | Existing retranscription path binds encounter authorization, source audio, transcript version/hash, and worker lease; stale or mismatched requests fail closed. | `tests/test_retranscription_workflow.py`: wrong asset, stale transcript, out-of-bounds span, and cross-tenant request checks pass; worker revalidates transcript digest before crop. | This verifies application authorization behavior in local fixtures, not a production multi-tenant deployment. |

## Repository-wide quality baseline

- Ruff check: passed after resolving 191 findings and restoring the canonical
  JSON helper import path used by ASR and review modules.
- Focused regression set (`test_retranscribe_span.py`,
  `test_uncertainty_classifier.py`, `test_chunk_integrity.py`): 5 passed.
- Selective retranscription workflow (`test_retranscription_workflow.py`):
  3 passed with synthetic audio and a stub local ASR adapter.
- Historical baseline replay (`test_baseline_summary.py`): 2 passed; the
  four denominators reconcile to the immutable scope-separated report.
- ASR evaluation contract (`test_asr_evaluation_contract.py`,
  `test_evaluation.py`): 23 passed, including failure-inclusive report
  generation and pre-inference rejection of incomplete manifests.
- Full-consultation edit replay (`test_asr_word_error_replay.py`): 1 passed;
  per-case counts sum to 679 edits / 5,204 reference words.
- Full application, ASR, and CI suites have not been established as green.

## Partially reconciled tasks

- **MTA-ASR-B01:** Added hash-bound lineage receipts with source asset hashes,
  transformation-manifest hashes, parent receipts and explicit timeline maps.
  Runtime ingest, channel isolation, bounded retranscription, Primock crops,
  role-track mixing, MedDistract lossless FLAC decoding, benchmark windows,
  conversation ablations, failure probes, and synthetic stress inputs now emit
  receipts. Multi-input transformations retain every parent digest. The
  detailed benchmark binds each run's source digest before creating crops.
  `tests/test_audio_provenance.py` and `tests/test_detailed_benchmark.py`: 8
  passed; media tests were skipped because PyAV is unavailable. Changed modules
  compile, Ruff check passes, and `git diff --check` passes. Historical reports
  and benchmark locks were not rewritten. Status: partial; this environment
  cannot execute PyAV normalization/FLAC integration, and resampler group-delay
  correction is explicitly unverified in its timeline map.

- **MTA-ASR-B02:** WAV inspection now rejects inconsistent RIFF/chunk bounds,
  unsupported PCM/float encodings, channel/sample-rate/bit-depth mismatches,
  invalid byte/block rates, partial frames, oversized files, and excessive
  duration before decode. Unsupported WAV encodings can no longer fall through
  to generic normalization. The PyAV decoder now checks stable input rate and
  channel metadata plus the resampler output profile per frame.
  `tests/test_wav_validation.py`: 12 passed, including 100 deterministic
  malformed headers and a queued worker failure that confirms no normalized
  result is published. Status: partial; PyAV is not installed, so decoder-frame
  consistency and supported-media decode cases remain unexecuted here.
- **MTA-ASR-B03:** Added a separate `energy_rms_v1` candidate with a canonical
  profile digest, source-audio digest, full frame mask, merged/padded time spans,
  and explicit uncalibrated-score labeling. A separate scorer reports missed
  and false-positive speech duration and time-coverage rates; reference spans
  are never passed to candidate generation. `tests/test_vad_candidates.py`: 3
  passed on synthetic PCM, including exact mask and duration accounting.
  Status: partial; this checkout has no source WAV fixtures for the annotated
  mock consultations, so false-negative/false-positive duration has not been
  measured against available annotated speech.

- **MTA-ASR-A04:** The frozen error-taxonomy artifact contains token-level edit
  rows tied by hashes to source reports and the reference manifest. Every
  reference substitution/deletion carries its reference token, role, and source
  turn interval; insertions remain explicitly unattributed with no invented
  timestamp. `tests/test_asr_critical_error_provenance.py` passed while checking
  all saved edit rows against their frozen source turns. However, this checkout
  has no WAV files in either the MedDistractAudio or full-consultation dataset
  directories, so direct replay of those intervals is unavailable. No remote
  audio was fetched. Critical name and dosing-frequency classification also
  needs further implementation. Status: partial; audio replay is
  `BLOCKED_MISSING_RESOURCE`.
- **MTA-ASR-A05:** Added `services/asr/subgroup_diagnostics.py` and the frozen
  development report `evaluation/reports/asr-subgroups-v1.json`. It summarizes
  saved edit errors by recording condition, annotated speaker role, overlap,
  reference-turn length, and annotated duration proxy. All 17 saved runs
  reconcile to 27,366 reference words in every dimension, including a
  13,683/13,683 clean/distracted split. `tests/test_asr_subgroup_diagnostics.py`:
  2 passed; it checks source digests, denominators, failure-inclusive missing
  outputs, and unknown channel mapping. Status: partial; annotated duration is
  not measured active speech time, channel metadata is unavailable, and there
  is no audio for validating channel or speech-time subgroups. These are
  descriptive saved-development diagnostics, not clinical acceptance.
- **MTA-ASR-A06:** Evaluation reports now label each sample as a processing
  failure, measured digital silence, successful empty output, nonempty output,
  or indeterminate legacy empty output. Empty text alone never implies silence;
  speech activity is explicitly `not_measured`. `tests/test_evaluation.py` and
  `tests/test_asr_evaluation_contract.py`: 23 passed, including denominator
  and contract checks. Existing frozen smoke evidence records two failed
  windows as failures and retains their references under the
  `empty_hypothesis_full_reference_deletions` policy. Status: partial; no
  available fixture establishes true empty speech versus non-silent silence,
  because no VAD evidence or source WAVs are available for those historical
  windows.

## Open gates

- The remaining addendum tasks are not verified by this progress record.
- The frozen <=5% normalized WER gate remains unchanged and has not been met by
  any newly evaluated configuration here.
- Real local inference, complete matched ablations, and independent clinical
  acceptance remain unverified or resource dependent.

- **MTA-ASR-B09:** Added an explicit resampled-timeline contract that records
  group delay in output frames and maps output frames monotonically back to
  source time only when both origin and delay are supplied. Unknown delay stays
  null, has no claimed error bound, and timestamp conversion fails closed.
  `tests/test_audio_provenance.py` covers measured-delay mapping, monotonicity,
  a half-output-sample error bound, and refusal when delay is unknown. Status:
  partial; PyAV/media normalization is unavailable here, so actual resampler
  delay has not been measured and runtime-normalized timestamps remain
  unverified.
- **MTA-ASR-B10:** Resource measurements above cover three enhancement
  transforms on all six available smoke clips. No longer approved local audio
  fixtures were available, so worst-case media duration, peak transient RSS,
  and full application memory admission remain unknown.
- **MTA-ASR-C01:** Added a source-only segmentation planner for fixed,
  overlap-aware, pause-aware, VAD cut-and-merge, and channel-first windows.
  Strategies carry frozen parameters and explicit source frame/channel
  positions. tests/test_asr_segmentation.py exercises all strategies.
  Status: partial; these plans are not yet wired into a single candidate
  evaluation runner and have not been compared on matched audio.
- **MTA-ASR-C03:** The planner emits a coverage ledger that detects omitted
  and duplicated annotated source spans; VAD and pause-aware candidates fail
  closed if the supplied speech spans are not covered. Tests cover gaps and
  overlap duplication. Status: partial; no annotated speech-span WAV set is
  available for measuring real source coverage, and the current ledger is a
  pure planner primitive rather than a runtime publication gate.
- **MTA-ASR-C04:** Added stitching that requires one output per stable segment
  ID, orders by source offsets, and deduplicates exact suffix/prefix tokens
  only when the windows overlap. Every removal is marked for audio review;
  non-overlapping repeated words are preserved. tests/test_asr_segmentation.py
  covers repeated edges, true non-overlap repetitions, and missing outputs.
  Status: partial; no measured word timestamps exist to disambiguate a true
  repeated word that happens at an overlapping window edge.
- **MTA-ASR-C05:** Added tunable VAD candidate minimum duration, maximum
  duration, and padding, preserving source sample offsets and checking supplied
  speech-span coverage. tests/test_asr_segmentation.py exercises short-span
  padding, duration limits, and coverage failures. Status: partial; thresholds
  have not been ablated against matched frozen conversations.
- **MTA-ASR-C06:** Added source-span diagnostics for omitted short turns,
  window-edge clips, partial coverage, joined known roles, and windows carrying
  unknown-role turns. tests/test_asr_segmentation.py verifies each category.
  Status: partial; no annotated conversation audio is available to generate
  measured boundary reports.
- **MTA-ASR-C09:** Added inverse source-frame/window-frame mapping keyed by
  stable window ID, returning channel identity where applicable. Round-trip
  tests cover fixed crops and channel-first windows. Status: partial; the
  helper covers same-rate sample-index crops; resampled audio must use the
  separate measured-delay mapping contract, and runtime transcript integration
  remains pending.
- **MTA-ASR-C08:** Added regression cases for exact shared suffix/prefix,
  backtracking around a shared medical phrase, and repeated metformin mentions
  in an overlap. tests/test_overlap_stitch_integrity.py exercises the existing
  sequence-alignment reassembler. Status: partial; alignment remains
  hypothesis-text-only and ambiguous repeated edge speech still requires
  original-audio review.
- **MTA-ASR-C07:** Added bounded context handoff requiring an explicitly
  acoustically reviewed prior span and a current candidate-speech signal;
  silent or indeterminate current windows receive empty context. Tests verify
  bounded carryover and silence suppression. Status: partial; this contract is
  not yet wired into a long-form decoder, and candidate activity is a VAD
  heuristic rather than proof of speech.
- **MTA-ASR-D02:** Added a typed ASR backend contract for inference,
  availability, timestamp capability, n-best capability, confidence
  capability, and runtime receipts. The faster-whisper adapter declares
  segment timestamps and explicitly unsupported n-best/confidence. Fake
  provider tests cover missing models, timeout exceptions, malformed output,
  and capability honesty. Status: partial; timeout propagation is tested as a
  provider failure, but no hard cancellation of a non-cooperative backend is
  implemented.
- **MTA-ASR-D03:** Added an Omi backend candidate wrapper that requires the
  exact local GGUF digest, pinned runtime and existing CPU library; automatic
  downloads are disabled. It reports text-only output with no native
  timestamps, n-best, or confidence. Added tests/test_omi_backend.py for
  rejecting missing weights before runtime initialization. Status: partial;
  the focused pytest process stalled before collection and did not complete,
  and no production worker profile or inference-mode promotion is configured.
- **MTA-ASR-D06:** Added normalized pairwise transcript disagreement with
  differing token spans. The output states that scores are uncalibrated,
  agreement is not truth, and no candidate selection occurs.
  tests/test_hypothesis_disagreement.py covers negation, dose substitution,
  agreement, and invalid candidate sets. Status: partial; thresholds have not
  been tuned against labeled disagreement cases and the diagnostic is not
  wired into runtime routing. Ruff and a direct substitution smoke check pass;
  focused pytest stalled before collection in this environment.
- **MTA-ASR-D10:** Added a fail-closed candidate admission gate that requires
  failure-inclusive WER at or below the unchanged 5% maximum, validated source
  timing, reviewed licensing, passed critical-safety review, and matched
  evaluation. Tests cover exact gate boundary and each denial reason. Status:
  partial; no deployment promotion command is wired to this policy, so current
  profiles remain explicitly not admitted.
- **MTA-ASR-D07:** Implemented and ran a post-hoc ROVER-style confusion-network
  vote on three frozen fixed-window engines over the same 16 consultation
  cases. Report evaluation/reports/rover-meddistract-detailed-v2-final.json
  SHA-256 4a47684f4b148bc57e8ce0bdde18665a108dfbc51e8cf39a3fae0063174b3f93
  binds all source report hashes, model configuration digests, the frozen
  suite, and the ROVER/scorer code hashes. ROVER: 5,617/27,366 edits (20.525%);
  faster-whisper large-v3: 5,798 (21.187%); Parakeet: 6,071 (22.184%); Omi:
  7,708 (28.166%). Two Omi failures are retained and mark those ROVER cases
  failed. tests/test_rover.py: 5 passed; Ruff and format checks pass. Status:
  partial; this unweighted voting baseline remains far above the 5% gate and
  has no clinical critical-token validation or inference-mode promotion.
- **MTA-ASR-D08:** Added a sequential backend pool that closes the active
  model before loading another, serializes requests, and fails closed on lock
  timeout or MemoryError. Its receipt explicitly says memory admission was
  not measured. Tests cover switching, contention, and resource failure.
  Status: partial; the pool is not wired into the application worker and no
  full-process memory or 16 GB hardware admission test has been run.
- **MTA-ASR-D09:** Generated a matched single/two-engine Pareto report from
  the frozen 16-case detailed runs. evaluation/reports/asr-compute-pareto-v1.json
  SHA-256 E909202756CF5D0F5383A9D81A14F3F86FA86F99878913C73EB82C7AA257B62C
  binds report, suite, model configuration, and code hashes. Single-engine
  p95 case wall RTFs: faster-whisper large-v3 2.082, Omi 0.294, Parakeet
  0.106. Sequential faster-whisper plus Parakeet p95 RTF: 2.186. Two-engine
  WER equals the faster-whisper pivot because two-way token ties favor pivot;
  all arms fail the 5% gate. Peak ASR memory and CPU seconds are explicitly
  unknown; targeted fallback was not evaluated. tests/test_asr_pareto.py:
  2 passed; Ruff and format checks pass. Status: partial; fresh resource
  measurements and a targeted-fallback arm remain outstanding.
- **MTA-ASR-D04:** Added a Parakeet ONNX backend implementing the common
  backend contract. It verifies the exact local artifact set and digests,
  requires onnx-asr 0.12.0, uses CPU execution, disables downloads, and
  declares text-only output without timestamps or confidence. Tests cover
  missing weights and truthful capability receipts. Status: partial; although
  frozen Parakeet benchmark outputs exist, this new adapter is not integrated
  into application selected-window routing.
- **MTA-ASR-E01:** Added a reproducible, provenance-bound English lexicon
  candidate artifact at evaluation/lexicons/clinical-english-v1-e01.json
  (SHA-256 af4b321287acd7762f6a9f63fe1ca29c4fc71ce0c52eda0ef95288efbfa4d142).
  The builder accepts only rights-reviewed, locked development manifests,
  rejects reserved acceptance groups, excludes uncertain reference rows, and
  records record/group IDs, reference hashes, offsets and dataset/manifest
  digests for each occurrence. It found one seed term (paracetamol) in eight
  licensed development references. tests/test_clinical_lexicon.py: 2 passed;
  Ruff and format checks pass. Status: partial; the seed inventory is only the
  existing five generic opt-in hints, this artifact does not validate clinical
  terminology, and no backend consumes it for decoding or reranking.
- **MTA-ASR-E02:** Added strict, immutable ASR clinical-entity schema kinds for
  drug name, strength, route, frequency, allergy, negation, anatomy, measurement
  and temporal relation. The current deterministic extractor emits only
  source-spanned medication and strength candidates, binds each strength to a
  medication, and keeps simple negated/uncertain clause status explicit.
  Tests disambiguate aspirin 75 mg from amlodipine 5 mg and a denied drug from
  an affirmed one; tests/test_asr_clinical_entities.py: 3 passed. Ruff and
  format checks pass. Status: partial; this heuristic covers only simple
  English clauses, is not clinically validated, and does not yet emit the
  other declared entity types or route/frequency relations.
- **MTA-ASR-E03:** Hardened the non-destructive ASR suggestion path. It now
  preserves a deep copy of raw segments, retains original text beside each
  proposal, marks every proposal review-required and non-adopted, and emits
  explicit reasons when medication identities or numeric/unit signatures
  differ. Invalid suggestion indexes fail closed. tests/test_asr_postprocess.py:
  3 passed; Ruff and format checks pass. Status: partial; this safeguards the
  helper contract, but the postprocessor is not yet the sole publication path
  for every runtime transcript workflow.
- **MTA-ASR-E04:** Wired the pinned faster-whisper `hotwords` decoder hook to
  an optional, hash-pinned lexicon selection. Only terms present in the E01
  provenance artifact are accepted; the adapter records candidate-only bias
  metadata and does not mutate text. The official faster-whisper interface
  documents `hotwords` as a decode hint. Focused adapter/context tests: 3
  passed; Ruff and format checks pass. Status: partial; this permits only the
  single term currently present in the lexicon, and no paired bias/no-bias WER
  or false-insertion evaluation has been run, so it is not an admitted profile.
- **MTA-ASR-E05:** Partial, resource-limited. The existing synthetic ASR
  challenge lists a generic `medical_homophone` case but contains no reviewed
  drug-name confusable pairs or clinical gold. The licensed development
  lexicon currently has one observed term, so it cannot support a meaningful
  sound-alike/abbreviation subgroup evaluation. Existing medication-binding
  checks cover explicit medication and dose swaps, but are not phonetic
  confusability evidence. No clinical correctness claim is made; completion
  requires an approved, rights-reviewed confusable set and reference labels.
- **MTA-ASR-E09:** Partial, metadata-limited. Audited the six frozen
  development dataset manifests; none declares accent/dialect labels. No
  accent subgroups or accent identity were inferred from audio or names.
  Accordingly no accent-related accuracy result is reported. Completion
  requires legally available English mock data with actual reviewed metadata
  and a sufficient matched denominator.
- **MTA-ASR-E06:** Added a finite candidate formatter limited to whitespace
  and case normalization for recognized numbers with supported explicit units.
  It verifies the before/after quantity signature, preserves the original
  string, never adds a missing unit, and never automatically adopts a
  candidate. Tests cover decimal/unit distinctions and unsupported or absent
  units; tests/test_asr_number_format.py: 3 passed and postprocess controls: 3
  passed. Ruff and format checks pass. Status: partial; no additional unit
  systems or app publication integration are claimed.
- **MTA-ASR-E08:** Ran a paired local faster-whisper tiny.en development pilot
  on four clean paracetamol-positive turns and four nearest non-target turns.
  evaluation/reports/asr-lexicon-bias-pilot-v1-final.json SHA-256
  d2fa02f5c7a894a8cdd57c7a6bd99136241aa1350c6b86cdd60e0150f0b616a7 binds
  the frozen dataset/lock, profile, lexicon and evaluator/adapter code hashes.
  Exact-term recall changed 1/4 to 4/4, while false insertions changed 0/4 to
  1/4 and normalized WER worsened from 44/153 (28.76%) to 46/153 (30.07%);
  no inference failures occurred. The result is development-only, not
  adjudicated clinical gold. Status: partial; this small pilot shows a
  non-target insertion and worse overall WER, and cannot justify enabling
  biasing or satisfy full-cohort validation.
- **MTA-ASR-E07:** Added an ASR candidate comparison wrapper around the
  conservative source-vs-claim rules. It flags negation-scope, medication,
  numeric/unit and medication-dose binding conflicts as review-required; it
  always keeps automatic adoption disabled and states that candidate
  agreement does not verify clinical truth. Mechanistic synthetic tests cover
  scope movement and aspirin/amlodipine dose swaps; tests/test_asr_clinical_entities.py:
  5 passed. Ruff and format checks pass. Status: partial; this comparison is
  rule-based, not clinically validated, and is not yet connected to every
  candidate workflow.
- **MTA-ASR-E10:** Extended correction-suggestion records to require a source
  audio ID and non-empty rationale, and to retain both original and proposed
  text with `human_review_state=pending`, `reviewed_by=null`, and
  `adopted=false`. Missing provenance or rationale fails closed.
  tests/test_asr_postprocess.py: 4 passed; Ruff and format checks pass. Status:
  partial; the helper is not yet connected to every app candidate/version
  workflow, and no human-reviewed terminology correction lifecycle is active.
- **MTA-ASR-F05:** Partial, backend-signal blocked. Current faster-whisper,
  Omi and Parakeet adapters all declare n-best and confidence unsupported;
  none exposes a validated acoustic likelihood for candidate ranking. No
  numeric candidate score is synthesized. Existing source-linked checks can
  flag inconsistencies but cannot rank which hypothesis was spoken. Completion
  requires a local decoder exposing valid acoustic evidence plus development
  calibration data and a frozen policy.
- **MTA-ASR-F07:** Added an early-exit eligibility rule that requires every
  reason-coded diagnostic to be explicitly present with provenance and clear;
  missing diagnostics or any observed risk routes to re-decode/review. Measured
  silence with empty text is separately identified. tests/test_asr_risk_selector.py:
  10 passed; Ruff and format checks pass. Status: partial; no upstream signals
  are wired into this rule, it does not yet save runtime compute, and recall of
  actual errors has not been measured.
- **MTA-ASR-F08:** Partial, annotation-limited. No clinician-adjudicated
  span-level critical-error labels or validated risk-selector outputs are
  available, so critical miss rate, safe-case false alarms, selected-audio
  coverage, and equal-compute random/control curves cannot be estimated
  honestly. Developer-authored synthetic fixtures remain mechanism tests and
  are not presented as coverage results. Completion requires reviewed
  development labels and matched selector/control inference receipts.
- **MTA-ASR-F09:** Partial, model-signal blocked. Faster-whisper, Omi and
  Parakeet adapters explicitly return confidence unsupported and uncalibrated;
  the deterministic risk score remains null. No reliability diagram or ECE is
  computed from heuristics or invented posteriors. Calibration work requires
  a backend with genuine score signals and a separate labeled development set.
- **MTA-ASR-F06:** Partial. Existing repair jobs cap each requested crop at
  120 seconds, validate source authorization/version/hash, admit model memory
  before inference, and retry worker jobs at most three times. Candidate output
  remains separate from the source transcript. No hard wall-clock cancellation
  is enforced inside a native model call; a lease heartbeat is not an
  inference timeout. A process-isolated inference deadline and end-to-end
  compute budget remain outstanding.
- **MTA-ASR-F04:** Extended advisory candidate checks so changes to negation
  and allergy polarity are explicitly flagged alongside drug and dose/unit
  changes. Raw wording remains immutable, all proposals remain pending review,
  and nothing is auto-adopted. tests/test_asr_postprocess.py: 5 passed; Ruff
  and format checks pass. Status: partial; the rule helper is not integrated
  into every text-generation/publication path and its heuristics are not
  clinically validated.
- **MTA-ASR-F10:** Added a deterministic immutable candidate-receipt builder
  binding audio and transcript IDs/digests, source span, original hypothesis,
  alternatives, decoder/profile digests, selection policy version, and
  abstention. Receipts preserve review-required/non-adopted status, reject
  reference-text fields, verify their semantic digest, and write exclusively.
  tests/test_asr_candidate_receipt.py: 3 passed; Ruff and format checks pass.
  Status: partial; current application retranscription does not yet persist
  this unified receipt, and deterministic inference replay is unverified.
- **MTA-ASR-G01:** Transcript segments now persist `timestamp_kind` separately
  from model-estimated segment bounds. Faster-whisper output is labeled
  `native_segment`; other engines default to `unknown`, and transcript-level
  word alignment is explicitly `not_provided`. tests/test_transcript_timestamp_integrity.py
  and test_timestamp_registry.py: 7 passed; Ruff and format checks pass.
  Status: partial; no native word timestamps or validated forced aligner are
  available, and segment bounds do not establish word alignment.
- **MTA-ASR-G02:** Partial, local-aligner blocked. Repository dependency and
  model inventories contain no validated English forced aligner. Existing
  timestamp checks reject malformed/out-of-bounds segment times and explicitly
  leave `word_alignment_validated=false`; they do not claim alignment proves a
  word was spoken. No acoustic support test for inserted words can be run until
  a qualified local aligner and independent audio-supported fixtures exist.
- **MTA-ASR-G03:** Existing audio provenance maps source PCM crops and
  channel selections to parent sample offsets, and resampled mappings fail
  closed unless source origin and group delay are measured.
  `tests/test_audio_provenance.py` covers crop mapping, measured resampling,
  monotonic offsets and unknown-delay rejection. Status: partial; mapping
  checks do not cover a forced-alignment runtime, which is unavailable under
  G02, or a full end-to-end alignment round trip.
- **MTA-ASR-G04:** Existing diarization output keeps `speaker_id` values
  separate from role labels; roles start `unknown`/`unconfirmed`, with
  clinician confirmation required. Channel-derived IDs are explicitly marked
  as not verified speakers, and observed-channel mapping never infers roles.
  `tests/test_diarization_policy.py` and `test_asr_evaluation_contract.py`:
  13 passed; Ruff passes. `test_channels.py` separately asserts unconfirmed
  roles. Status: partial; no identity/role accuracy or clinician confirmation
  has been established for these R&D runs.
- **MTA-ASR-G05:** Partial. `evaluation/reports/speaker-comparison-2026-10-26.json`
  contains matched fixed-window and separate-channel conditions for three
  consultations, with DER and role error timing. References are upstream
  TextGrid labels and optimal scoring mappings are not role confirmations.
  No VAD-turn diarization arm is included, so the requested three-way modality
  comparison is incomplete; clinical speaker accuracy is not claimed.
- **MTA-ASR-G06:** Existing subgroup report
  `evaluation/reports/asr-subgroups-v1.json` (SHA-256
  3d65850d0248a9ff516a51baf53ea8a3dd610b7a861e9d29a80ec0c653c67852)
  disaggregates overlap status, reference role and turn length; segmentation
  diagnostics separately mark omitted short turns and boundary clipping.
  tests/test_asr_subgroup_diagnostics.py and test_asr_segmentation.py: 13
  passed; Ruff passes. Status: partial; upstream mock annotations are not
  adjudicated, and no standalone overlap detector or validated missed-short-
  patient-turn rate has been established.
- **MTA-ASR-G07:** Existing `SpeakerRoles` UI provides audio preview and
  explicit role assignment; the API requires clinician confirmation and
  `If-Match` against the current transcript before creating a new version.
  UI and backend preserve the historical source versions. Status: partial;
  reviewers cannot yet split, merge or reassign individual turns between
  anonymous speaker clusters, and a complete stale-note invalidation workflow
  has not been verified end to end for these edits.
- **MTA-ASR-G08:** Existing failure-inclusive subgroup reports separate
  patient and clinician reference-role edits; the detailed development run
  preserves unknown roles rather than coercing them. Status: partial; no
  patient-prioritized runtime quality control or medically critical patient
  omission measure is wired, and upstream role annotations are not independently
  adjudicated.
- **MTA-ASR-G09:** Existing transcript outputs remain `review_required`, carry
  `speaker_unassigned`/unconfirmed role flags, and mark timing gaps as
  untranscribed with unknown cause. Role-dependent fact checks require
  confirmation or block approval rather than moving evidence across speakers.
  Status: partial; policy behavior is covered by transcript/review tests, but
  there is no comprehensive UI test proving every clinically role-dependent
  workflow blocks on unknown timing and role metadata.
- **MTA-ASR-G10:** Partial. Current HTTP-to-worker integration tests exercise
  crop, cancellation, resource contention and candidate publication using
  generated fixtures/stub adapters; public-audio benchmark runs are separate
  offline evaluation jobs. The full real-worker matrix across mono/stereo,
  silence, clipping, crosstalk and interrupted model inference has not been
  executed, so no real-worker speaker/timing accuracy claim is made.
- **MTA-ASR-H01:** Partial. `docs/device-profile.md` defines one x86 CPU
  workstation with at least four threads and 16 GB RAM, without an assumed GPU.
  The frozen detailed set contains eight unique consultation groups across 16
  paired clean/noisy recordings (1.32 recorded hours, with shared source
  content across conditions); labels are upstream mock references and are not
  independently adjudicated. This supports offline inference experiments, not
  training a speech foundation model from scratch. A credible FLOP/time estimate
  is unavailable without a selected architecture and measured training
  throughput; no from-scratch training is claimed or attempted.
- **MTA-ASR-H02:** Partial. Current benchmark source manifests and local model
  profiles bind dataset/model revisions and license identifiers; lexicon
  construction further requires rights-reviewed development manifests and
  verified locks. No gated or restricted model/data was used in the reported
  local runs, and no derived training artifact exists. This is a preflight for
  the evaluated assets, not authorization to train on any additional source;
  each future training input and derived artifact needs its own rights review.
- **MTA-ASR-H03:** Partial. Development manifests identify consultation-group
  IDs, and `evaluation/acceptance-reservation-v1.json` reserves three groups
  before inference for future independent annotation. Current evaluation uses
  development groups only; there is no training split or training manifest
  because no adaptation has been run. Group separation does not prove speaker,
  site, device or model-training independence, and no shared-speaker leakage
  check is possible from the available metadata.
- **MTA-ASR-H04:** Not run. No training augmentation artifacts were generated.
  Existing gain/filter/noise-suppression work is paired inference-time signal
  processing with source provenance; it is not relabeled training data or a
  training augmentation gain. Any future licensed development augmentation
  needs reproducible seeds, parent/derived hashes and label-preservation checks.
- **MTA-ASR-H05:** Not run. Existing ROVER and hotword experiments are
  inference-time candidate generation/decoding comparisons, not trained
  correction or reranking components. No cross-fitted training table was
  created; reserved acceptance groups remain excluded. A future confusion
  table would need group-level train/development boundaries and source-linked
  labels before any component is fit.
- **MTA-ASR-H06:** `BLOCKED_MISSING_RESOURCE`. Existing inference profiles
  provide converted/quantized decoder artifacts, not an approved training
  architecture, optimizer recipe or adapter checkpoint. The reference host has
  CPU-only capacity and no qualified training accelerator; no LoRA/rescoring
  training has been simulated or claimed.
- **MTA-ASR-H07:** `BLOCKED_MISSING_RESOURCE`. No candidate has genuine
  calibrated acoustic scores or a disjoint group-level calibration corpus;
  current backend confidence is explicitly unsupported. F09 records the same
  evidence gap. No reliability curves or selection thresholds are fabricated.
- **MTA-ASR-H08:** `BLOCKED_MISSING_RESOURCE`. No independently verified
  clinician-confirmed correction set is available. Existing UI edits are
  source-versioned operational corrections, not research training labels;
  synthetic fixtures and developer-authored proposals are never treated as
  clinician signatures or automatic self-training input.
- **MTA-ASR-H09:** Partial. `services/asr/removal_propagation.py` now rebuilds a
  lexicon and retraining manifest without revoked source references, drops
  contaminated training rows, and invalidates derived model artifact records
  for retraining. Its synthetic acceptance test verifies no revoked lineage
  remains and that source objects are not mutated (`tests/test_asr_removal_propagation.py`:
  2 passed). It does not claim to erase learned weights. No real correction
  corpus or trained artifact exists here, and integration into a live correction
  or training pipeline remains unverified.
- **MTA-ASR-H10:** No adaptation-attributable gain is established (`null`).
  No correction model, LoRA adapter or rescoring model was trained. The E08
  hotword pilot changes decoding only and worsened aggregate WER on its small
  matched subset; it cannot be credited as an adaptation gain.
- **MTA-ASR-I01:** Partial. `evaluation/selection-policy.json` and frozen
  evaluation contracts predeclare failure-inclusive normalized WER and retain
  the unchanged <=5% ceiling; existing reports cannot weaken it. Clinical
  critical-error and patient-role non-inferiority tolerances are still pending
  a clinical owner, and no independent adjudicated acceptance set is available.
  The primary WER endpoint is frozen, but the safety-gate preregistration is
  incomplete.
- **MTA-ASR-I02:** Partial. Existing frozen reports provide identical-input
  comparisons for fixed/overlap/speech-aware/context segmentation and for
  matched decoder/consensus arms; the E08 term-bias pilot also pairs baseline
  and biased decoding on identical crops. The full declared matrix (VAD-only,
  terminology-only, repair-only and full pipeline under equal compute) has not
  been run on one frozen cohort, so no end-to-end method attribution is claimed.
- **MTA-ASR-I03:** `FAIL` for every currently evaluated model/system profile.
  The unchanged admission ceiling is normalized WER <=5%; the best expanded
  short-clip model result is still 8.70%, and full-consultation/detailed runs
  are worse. D10's gate remains fail-closed and no inference-mode promotion is
  allowed. Relative improvement does not change this result.
- **MTA-ASR-I04:** `BLOCKED_MISSING_RESOURCE`. The admission policy requires
  separate critical insertion/substitution/omission and role-safety review,
  but no independently adjudicated clinical annotations or owner-approved
  tolerances are available. The E08 pilot's false insertion is a development
  signal, not a clinical error rate. Abstentions remain review-required and
  cannot be counted as successful corrections.
- **MTA-ASR-I05:** Engineering system path is now exercised by
  `tests/test_real_local_asr_workflow.py`: the existing licensed PriMock57
  patient utterance passes through upload, PCM ingest, the actual locally
  installed tiny.en Faster Whisper model, immutable native-timestamped
  transcript, versioned source review, note verification, approval and
  integrity-checked JSON export. The test passed against the current local
  model artifacts. Review and approval actions are scripted for this public
  mock fixture; they do not represent clinician review, clinical validity or
  user acceptance. The frozen WER and independent safety gates remain separate.
- **MTA-ASR-I06:** Partial. High-risk medication, dose/unit, negation and
  allergy edits are emitted as pending, non-adopted suggestions while original
  ASR text remains intact (`tests/test_asr_postprocess.py`: 5 passed). Transcript
  edits create immutable child versions and stale approvals fail closed; span
  retranscription checks bind to the current source/audio. This is software
  guard coverage only: the broader review/retranscription workflow test command
  did not finish in this run, and coverage does not establish clinician review
  quality. No automatic adoption path was found in these reviewed correction
  modules.
- **MTA-ASR-I07:** Partial. `evaluation/reports/paired-asr-bootstrap-v1.json`
  reports paired clean-versus-distracted WER deltas using consultation-level
  resampling (10,000 deterministic iterations, 95% percentile intervals) and
  records both arms and failed statuses for each pair. It is a development-only
  convenience sample. The report does not stratify paired uncertainty by
  clinical term or speaker, and preserved failure statuses are not adjudicated
  clinical error estimates; the requested full uncertainty analysis remains
  incomplete.
- **MTA-ASR-I08:** Partial. Existing compute Pareto receipts report measured
  case wall time and RTF percentiles for selected inference profiles; worker
  receipts also retain per-job wall time. The Pareto report explicitly leaves
  ASR peak memory unknown, and no end-to-end successfully completed consultation
  cost (including resource amortization) is measured. These profile-level
  inference timings do not satisfy the requested full consultation metrics.
- **MTA-ASR-I09:** Partial. Model cards and a negative-experiment index exist,
  and benchmark receipts bind runs to dataset/model/source digests. However, the
  index is a bounded historical inventory and the reporting artifacts do not
  currently provide one reproducible publication package with every requested
  ablation/error table regenerated from source-bound receipts. Clinical-gold
  and admission claims remain explicitly absent.
- **MTA-ASR-I10:** Partial. Synthetic tests cover digital-silence hallucination
  rejection, cross-talk detection, repeated-token stitching integrity, and
  source/candidate safety guards. `tests/test_adversarial_cases.py` records only
  synthetic cases and explicitly has no clinical gold. There is no complete
  audio-level suite for low-volume patient denial, deceptive spoken prompts and
  corrupt media through the real ASR worker; resulting-note non-approval is
  therefore not established across the requested challenge set.
- **MTA-ASR-I12:** Defined in `evaluation/asr-capability-matrix-v1.json`.
  It distinguishes verified local CPU profiles, conditional/unqualified CUDA
  profiles, and missing/corrupt weights (unavailable, no automatic download).
  All rows preserve the independent clinical/WER admission gate. CUDA remains
  a conditional statement, not a hardware validation result.
- **MTA-ASR-I11:** `BLOCKED_MISSING_RESOURCE` for the requested release check.
  The repository CI workflow declares Python quality/full-suite, frontend,
  PostgreSQL and container jobs, but GitHub returned no status checks for the
  current source commit `8d93b88f4a170d12e2e64a7b28a3ae23e1fb9060`. The latest
  available local acceptance receipt is from an earlier source commit and
  records a timed-out full backend run plus missing PyAV, PostgreSQL DSN and
  Docker. Those results are not promoted as exact-HEAD evidence; all required
  exact-HEAD CI lanes remain unverified.
- **MTA-ASR-I13:** Partial. The clinician source-review screen supports
  keyboard-operated source-interval playback, transcript text edits, and saving
  corrections as a new version. The read-only ASR error-review packet shows
  waveform clips/audio, source intervals and candidate alternatives, but is a
  research/development tool, not the clinician queue. The clinician screen does
  not present reason-coded ASR alternatives as an uncertain-span queue, and no
  scripted usability acceptance was run for that workflow.
- **MTA-ASR-I14:** Published `evaluation/reports/asr-objective-release-v1.json`
  with objective-level `FAIL`/`BLOCKED_MISSING_RESOURCE` decisions for model
  qualification, clinical safety, end-to-end product acceptance and engineering
  CI. Missing evidence is never treated as PASS; the report authorizes no model
  promotion or clinical use.
- **MTA-ASR-I13 update:** Implemented a clinician-facing uncertain-span queue in
  the source review screen. It lists original transcript text, known uncertainty
  reasons, supplied alternatives when present, and untranscribed source
  intervals; keyboard activation seeks to the source and focuses its versioned
  editor. TypeScript and the production build pass. The browser usability test
  could not navigate to the local test server (`ERR_NETWORK_ACCESS_DENIED`), and
  current ASR profiles do not supply alternate hypotheses or a rendered
  waveform, so full I13 acceptance remains incomplete.
- **MTA-ASR-I05 update:** A separate invocation through the pinned tiny.en
  adapter on the locked PriMock57 patient smoke clip succeeded, produced two
  native-timestamped segments, and reported 1.33 seconds inference time after
  model load. This is real model evidence but not a full system run. The local
  application-test harness stalls on its first in-process HTTP request even for
  the pre-existing synthetic transcription workflow; the added integration
  attempt was removed rather than retaining a hanging test. The full
  audio-to-approved-export acceptance remains incomplete.
- **MTA-ASR-I05 integration update:** The prior transport stall was traced to
  the sandbox denying the Windows asyncio loopback socket used by Starlette's
  `TestClient`; it was not an application-route deadlock. With permitted
  loopback for the isolated test, the new real-model workflow test completed
  audio upload through integrity-checked approved export (1 passed). This is
  reproducible engineering-path evidence only: the review/approval actions are
  scripted and do not close independent clinical acceptance.
- **MTA-ASR-I13 waveform update:** The clinician uncertain-span queue now
  renders source-bound waveform peaks and highlights each selected transcript
  or untranscribed interval. The authenticated API checks the stored audio hash
  and returns at most 160 amplitude bins, optionally for a selected channel;
  the browser does not decode a full recording into memory. The production
  frontend build and tests/test_audio_waveform.py pass, and
  apps/clinician-web/e2e/uncertain-span-waveform.spec.ts passed against the
  isolated synthetic browser fixture. I13 remains partial because the
  installed ASR backends do not provide alternate hypotheses; no alternatives
  are invented.
- **MTA-ASR-I14 update:** Published
  evaluation/reports/asr-objective-release-v3.json, source-bound to commit
  e5da4cd5258d25cd6ffe908eeb3cb81f73d9b113. It adds the waveform browser
  evidence while retaining FAIL for model qualification and product acceptance,
  and BLOCKED_MISSING_RESOURCE for clinical safety and exact-HEAD release CI.
  Versions v1 and v2 remain preserved.
- **Addendum reconciliation:** All 95 checklist IDs are represented in
  evaluation/asr-task-ledger-v1.json with their requirement, acceptance text,
  direct progress evidence, and conservative status. Evidence recorded is not
  treated as a completion claim. The ledger binds the addendum and this progress
  record by SHA-256 and preserves the 5% WER ceiling.
- **MTA-ASR-I14 update:** Published
  evaluation/reports/asr-objective-release-v2.json, source-bound to commit
  cf538fc33a1975121af7add8ee70438aca87c561. It records the real-model
  engineering-path result while retaining FAIL for product acceptance and
  model qualification, and BLOCKED_MISSING_RESOURCE for clinical safety and
  exact-HEAD release CI. The earlier v1 decision remains preserved.
- **MTA-ASR-C02:** Verified and regression-pinned the current full-consultation
  fixed-window baseline before further segmentation claims. The source-bound
  ranking identifies `omi-med-stt-v1-native-empty` first at 16.41% clean / 17.22%
  distracted WER. Its matched overlap and speech-aware arms score worse in both
  conditions; each arm has 8 foregrounds, 13,683 reference words and zero failed
  samples. `tests/test_fixed_window_baseline.py`: 1 passed; it checks exact report
  hashes, manifest/suite bindings, common denominators, and the unchanged 5% gate.
  This confirms only the development baseline; every arm still fails admission,
  and it does not qualify Omi for clinical use.
- **MTA-ASR-C10:** Partial and still open. The source-bound v4 large-v3 fixed
  run contains all 16 records (8 clean, 8 distracted), with 0 failed samples.
  It exactly reproduces the immutable v2 fixed-mode edit counts and denominator:
  clean 20.69% WER (2,831/13,683) and distracted 21.68% (2,967/13,683), both
  above the unchanged 5% gate. Fresh full-run latency is 6,416.6 / 6,489.1
  seconds; peak resident memory is 3,444,953,088 bytes (Windows peak working set,
  model-load-inclusive) against the 16 GiB cap. The source-bound v3 large-v3
  speech-aware receipt also has all 16 cases (8 per condition), with 0 failed
  samples, but reuses 14 v2 cases: its 7,848.8 / 7,663.1 second condition
  totals include historical timing and its 3,156,635,648-byte resource receipt
  covers the resumed process and two new cases only. C10 still lacks fresh
  full-run resource/latency receipts for the other predeclared modes and the
  complete candidate matrix; no C10 completion claim is made.
- **MTA-ASR-C10 instrumentation update:** New benchmark receipts now capture
  process peak resident bytes, measurement method, model-load-inclusive scope,
  resumed/full cohort scope, and the budget verdict. The source-bound
  detailed-suite-v4 refreshes the frozen execution-source hashes and fixes a
  16 GiB process RSS ceiling with one local model
  process. Historical reports are unchanged; no C10 mode is considered complete
  from instrumentation alone.
- **MTA-ASR-C10 large-v3 speech-aware resume:** `evaluation/detailed-suite-v3.json`
  validated and resumed the 14-case v2 receipt by exact file hash, then ran the
  two missing `day1_consultation08` conditions. `evaluation/runs/meddistract-detailed-v3/faster-whisper-large-v3.speech_aware.json`
  is complete at 16/16 with no failed samples and includes the resumed-suffix
  resource measurement. Its report SHA-256 is
  `223635a95466d9d2752d09277b522f5b052ceccf634b9d7efab1d567a7aedc23`.
- **MTA-ASR-C10 large-v3 fixed full run:** `evaluation/detailed-suite-v4.json`
  source-bound a fresh 16-case run after Ruff changed the v3 execution source.
  The report `evaluation/runs/meddistract-detailed-v4/faster-whisper-large-v3.fixed.json`
  matches v2 edit counts exactly, reports fresh per-condition latency and a
  full-process peak working set, and remains a development failure at the 5%
  gate. `tests/test_detailed_benchmark.py::test_detailed_v4_large_v3_fixed_receipt_is_full_and_reproduces_baseline`
  passed (1 test), checking all manifest cases, coverage, failure inclusion,
  immutable edit counts, the 5% gate and full-run memory budget. Its SHA-256 is
  `05da2b5a3004cc9d91e45acdd857abaf70fc00b0b1586706249d0958b2fa1840`.
- **MTA-ASR-C10 large-v3 overlap full run:** Suite v4 ran all 16 manifest cases
  afresh (8 clean/8 distracted), with complete source coverage and zero failed
  cases or chunks. The new receipt reproduces the immutable v2 overlap edits
  exactly: clean 3,228/13,683 (23.5913%) and distracted 3,306/13,683
  (24.1614%). Per-condition wall time was 6,585.5/6,608.3 seconds; model load
  took 41.3 seconds. Full-process peak working set was 3,445,260,288 bytes,
  within the unchanged 16 GiB budget. The <=5% admission gate remains FAIL.
  `tests/test_detailed_benchmark.py::test_detailed_v4_large_v3_overlap_receipt_is_full_and_reproduces_baseline`
  pins the report SHA-256 `7a0df4c190b9314126b9dda0ec6f1602dd67d18029e3fd1534071c0833c702ca`,
  case/coverage/failure accounting, exact historical scores, the WER gate and
  resource receipt. C10 remains partial: other modes and candidates still need
  fresh full-run latency and memory measurements.
- **MTA-ASR-C10 large-v3 speech-aware fresh full run:** Suite v6 supersedes v5
  and removes the large-v3 historical resume source; suite and manifest hashes
  match, and all seven bound source hashes matched before inference. All 16
  cases were newly inferred with full coverage and zero failed cases/chunks.
  The receipt exactly matches the prior complete speech-aware edit counts:
  clean 3,211/13,683 (23.4671%) and distracted 3,293/13,683 (24.0664%). Fresh
  per-condition wall time was 4,979.1/4,985.7 seconds after a 35.5-second model
  load. Full-process peak working set was 3,445,854,208 bytes, within 16 GiB.
  Both results fail the unchanged <=5% admission gate. The regression
  `tests/test_detailed_benchmark.py::test_detailed_v6_large_v3_speech_aware_receipt_is_fresh_and_full`
  passed with the no-resume suite regression; report SHA-256 is
  `5a7ff8607521bcb0fb1764b358162358e8281f4397e40b01dfe9e4518144c0b9`.
  C10 remains partial pending fresh receipts for the remaining modes/candidates.
- **MTA-ASR-C10 Whisper-small fixed full run:** Suite v6 ran all 16 manifest
  cases without a resume source, with complete coverage and zero failed cases
  or chunks. The report exactly reproduces immutable v2 counts: clean
  3,477/13,683 (25.4111%) and distracted 3,970/13,683 (29.0141%). Fresh
  per-condition wall time was 1,322.9/1,376.4 seconds after a 19.0-second model
  load. Full-process peak working set was 743,542,784 bytes, within 16 GiB.
  Both conditions fail the unchanged <=5% WER admission gate. Regression
  `tests/test_detailed_benchmark.py::test_detailed_v6_whisper_small_fixed_receipt_is_full_and_reproduces_baseline`
  passed, binding the full case set, historical edit counts, gate and resource
  measurement. Report SHA-256 is
  `5ba7cb52dc17d98932790f2456d0975b52da89afed30452cf5d08a808558ff36`.
  C10 remains partial pending the other predeclared modes/candidates.
- **MTA-ASR-C10 Whisper-small overlap full run:** Suite v6 ran all 16 manifest
  cases without a resume source, with complete coverage and zero failed cases
  or chunks. Clean scored 3,846/13,683 (28.1079%); distracted scored
  3,978/13,683 (29.0726%). Per-condition wall time was 2,214.1/2,523.9 seconds
  after a 3.3-second model load. Full-process peak working set was 743,825,408
  bytes, within 16 GiB. Both conditions fail the unchanged <=5% WER gate.
  There is no immutable v2 Whisper-small overlap receipt, so this is recorded as
  a new arm, not a baseline reproduction. The suite's source hashes matched the
  source files before launch; a later shared-worktree edit changed
  `services/detailed_benchmark.py`, and the runtime revision object is absent
  from the current local git object store, limiting after-the-fact source
  replay. Regression
  `tests/test_detailed_benchmark.py::test_detailed_v6_whisper_small_overlap_receipt_is_full_and_failure_inclusive`
  passed for the full cohort, coverage, failure accounting, gate and resource
  budget. Report SHA-256 is
  `ee841e73ba7a83cea31a2d7f1077c389991606bfedcd4ce7298584c96b4f5b90`.
  C10 remains partial pending the other predeclared modes/candidates.
- **MTA-ASR-D01:** The operational application path remains the pinned
  Faster Whisper 1.2.1 adapter. `ASRProfile` freezes decoder configuration
  (`beam_size=5`, English, CPU INT8 by default), profile/artifact hashes are
  included in runtime receipts, and the adapter uses deterministic decoding
  options (`temperature=0`, VAD off, no previous-text conditioning). The
  backend contract regression checks native segment timestamps, profile hash,
  and unsupported confidence. No alternate decoder was promoted. This records
  the preserved contract; exact deployment profile regressions still need to
  run on the target deployment host.
- **MTA-ASR-D05:** Partial. The pinned Faster Whisper adapter now preserves its
  native winning-sequence token IDs and segment average log probability in the
  immutable transcript. The receipt explicitly labels this as one-best decoder
  evidence, with n_best_supported=false and calibrated=false; it is not a
  confidence estimate. Omi and Parakeet continue to declare n-best/confidence
  unsupported. Backend and transcript regressions validate native meaning and
  reject invalid scores; see tests/test_asr_decoder_evidence.py and
  tests/test_asr_optional_runtime_dependencies.py. Multiple hypotheses and
  calibrated uncertainty remain unavailable.
- **MTA-ASR-I15:** Research summary and paper section are present in
  `docs/asr-rnd-research-section.md`, covering the hypothesis, method,
  baselines, negative findings, novelty limits, ablation gaps, ethics and
  reproducibility pointers. No novel clinical acoustic reranking claim is
  made; related-work comparison and the full matched-compute ablation matrix
  remain open.
- **MTA-ASR-C10 Omi fixed full run:** The immutable suite-v7 lock binds the run
  to main commit `fb21680` and its seven execution-source hashes; the locked Omi
  job has no resume source. One later shared-worktree edit changed
  `services/detailed_benchmark.py`, so current working-tree source is not passed
  off as the benchmark source. The fresh report
  covers all 16 manifest cases and all audio input, while retaining two failed
  chunks (one clean and one distracted) as failed samples in the aggregates.
  Clean scored 3,809/13,683 edits (27.8375%) and distracted 3,899/13,683
  (28.4952%); both fail the unchanged <=5% WER gate. Condition wall times were
  1,939.8/1,931.8 seconds. Full-process peak working set was 1,273,974,784
  bytes, and process CPU was 11,780.5 seconds; both fit the declared resource
  budget. The report SHA-256 is
  `8d2da60b8e77f8d70ba1bdaff05532904864a8112d9419ba35701d3bc8dad6da`.
  A focused regression pins the suite, manifest, complete cohort, both failed
  chunks, failure-inclusive condition totals, 5% gate and resource receipt.
  This negative arm does not establish model qualification. C10 remains partial
  because the predeclared mode/candidate matrix is still incomplete.
- **MTA-ASR-C10 Omi native-empty fixed ablation:** Suite v7 ran all 16 manifest
  cases afresh with complete audio coverage and zero failed cases/chunks. This
  same-weight wrapper explicitly accepts the documented native zero-token
  response; all other errors remain failures. Clean scored 2,245/13,683 edits
  (16.4072%) and distracted 2,356/13,683 (17.2184%), versus the regular Omi
  fixed arm's 3,809 and 3,899 edits. This is a development signal for the
  wrapper's empty-response handling, not qualification; both results fail the
  unchanged <=5% WER gate. Wall time was 1,331.6/1,296.8 seconds, full-process
  peak working set 1,265,270,784 bytes, and CPU 9,665.7 seconds. The report
  SHA-256 is
  `cfc25c0a8b1334d7a28f357d498eb60ea24aca678c5c688960f551c1f355b68e`.
  The focused regression binds the fresh suite, manifest, full coverage,
  failure-inclusive scoring, unchanged gate and resource receipt. C10 remains
  partial pending the remaining modes and candidates.
- **MTA-ASR-C10 tiny.en fixed fresh baseline reproduction:** Suite v7 ran all 16
  manifest cases with full audio coverage and zero failed cases/chunks. It
  exactly reproduces the immutable v2 counts: clean 4,415/13,683 (32.2663%)
  and distracted 4,689/13,683 (34.2688%). Fresh condition wall times were
  264.7/272.7 seconds after a 6.8-second model load. Full-process peak working
  set was 280,338,432 bytes and CPU was 2,043.7 seconds, within the 16 GiB
  budget. Both conditions fail the unchanged <=5% gate. The receipt SHA-256 is
  `06da69961c07be44c3de5c72f799a78d031b0748a1231931e483eee0ae7ef6cd`.
  Its focused regression binds the complete fresh cohort to the v2 edit counts,
  gate and process-level resource receipt. C10 remains partial while other
  predeclared modes and candidates lack fresh receipts.
- **MTA-ASR-C10 Whisper-small fixed fresh baseline reproduction:** Suite v7
  ran all 16 manifest cases without a resume source, with complete coverage and
  zero failed cases/chunks. It exactly reproduces immutable v2 edits: clean
  3,477/13,683 (25.4111%) and distracted 3,970/13,683 (29.0141%). Fresh
  condition wall time was 1,331.5/1,340.8 seconds after a 7.3-second model
  load. Full-process peak working set was 744,091,648 bytes and CPU was
  10,236.2 seconds, within the 16 GiB budget. Both conditions fail the
  unchanged <=5% gate. The report SHA-256 is
  `07fbb9a170bc49c26a2c69624971db60d0df2587fbad540cd54566800b2e9ba4`.
  The focused regression binds fresh coverage to baseline edits, gate and
  measured resources. C10 remains partial while other predeclared candidates
  and modes remain incomplete.
- **MTA-ASR-C10 Multimed Whisper-small fixed fresh baseline reproduction:**
  Suite v7 ran all 16 manifest cases with complete input coverage and zero
  failed cases/chunks. It exactly reproduces immutable v2 counts: clean
  7,281/13,683 (53.2120%) and distracted 6,994/13,683 (51.1145%). Fresh
  condition wall times were 1,561.5/1,664.5 seconds after a 3.8-second model
  load. Full-process peak working set was 650,498,048 bytes and CPU was
  12,234.5 seconds, within 16 GiB. Both WERs fail the unchanged <=5% gate.
  Report SHA-256 is
  `da396fb055fe4fb975e88de9715c7c033602bbf17e61c38b35f5aee1f34b58f8`.
  Its focused regression binds the fresh cohort to baseline scores, gate and
  resource measurements. This negative candidate result leaves C10 partial.
- **MTA-ASR-C10 Parakeet fixed fresh baseline reproduction:** Suite v7 ran all
  16 manifest cases with complete input coverage and zero failed cases/chunks.
  It exactly reproduces immutable v2 counts: clean 2,985/13,683 (21.8154%) and
  distracted 3,086/13,683 (22.5535%). Fresh condition wall times were
  582.6/608.3 seconds after a 15.1-second model load. Full-process peak
  working set was 1,300,725,760 bytes and process CPU was 4,552.7 seconds,
  within the 16 GiB budget. Both WERs fail the unchanged <=5% gate. Report
  SHA-256 is `6aeda83ecafb1f7bfd48eaf7660521ed15ffdc14eeec48ee6babb1fd45333694`.
  A focused regression binds full fresh coverage to baseline edits, the gate
  and measured resources. C10 remains partial pending other candidate arms.
