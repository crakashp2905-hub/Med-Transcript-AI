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
