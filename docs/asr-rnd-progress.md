# In-house ASR R&D progress

This progress record tracks work against the 95-item in-house ASR addendum. The
addendum's benchmark and admission claims remain unchanged. Code and synthetic
tests do not establish ASR accuracy, clinical validity, or external acceptance.

## Completed engineering tasks

| Task | Result | Evidence | Limits |
|---|---|---|---|
| MTA-ASR-A01 | Verified the historical WER baselines as four distinct scopes; no aggregate cross-cohort ranking. | `scope-separated-baselines-v1.json` SHA-256 `c9b84529a7b27c6e85d0c8857b0091b6`; denominators are 197/2,264 short clips, 679/5,204 three consultations, 2,245/13,683 clean, and 2,356/13,683 distracted. `tests/test_baseline_summary.py`: 2 passed; its replay verifies pinned source digests. | Historical benchmark replay only; all four configurations fail the unchanged 5% gate. |
| MTA-ASR-A02 | Added a strict offline evaluation contract binding rights-reviewed manifests, recording hashes, consultation groups, channel observations/maps, reference digests, local model revision, decoder settings, normalization, and failure-inclusive denominators. | `services/asr/evaluation_contract.py` is enforced by `services/evaluation.py` before inference and before writing the report. Contract tests cover the three existing public sample manifests, malformed-manifest rejection before model invocation, contract digest tampering, and a failed sample retained in the reference denominator. `tests/test_asr_evaluation_contract.py` plus `tests/test_evaluation.py`: 22 passed. | Uses the current sample-based local faster-whisper evaluation adapter. It does not validate full-consultation reports or establish model accuracy. |
| MTA-ASR-F01 | Implemented deterministic span risk records in `services/asr/risk_selector.py`. | `tests/test_asr_risk_selector.py`: 8 passed; Ruff check and format pass. | Mechanistic unit evidence only. Signals must be produced by validated upstream diagnostics; this selector does not measure audio or infer calibrated confidence. |
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
  `test_evaluation.py`): 22 passed, including failure-inclusive report
  generation and pre-inference rejection of incomplete manifests.
- Full application, ASR, and CI suites have not been established as green.

## Open gates

- The remaining addendum tasks are not verified by this progress record.
- The frozen <=5% normalized WER gate remains unchanged and has not been met by
  any newly evaluated configuration here.
- Real local inference, complete matched ablations, and independent clinical
  acceptance remain unverified or resource dependent.
