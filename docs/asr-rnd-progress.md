# In-house ASR R&D progress

This progress record tracks work against the 95-item in-house ASR addendum. The
addendum's benchmark and admission claims remain unchanged. Code and synthetic
tests do not establish ASR accuracy, clinical validity, or external acceptance.

## Completed engineering tasks

| Task | Result | Evidence | Limits |
|---|---|---|---|
| MTA-ASR-F01 | Implemented deterministic span risk records in `services/asr/risk_selector.py`. | `tests/test_asr_risk_selector.py`: 8 passed; Ruff check and format pass. | Mechanistic unit evidence only. Signals must be produced by validated upstream diagnostics; this selector does not measure audio or infer calibrated confidence. |

## Repository-wide quality baseline

- Ruff check: passed after resolving 191 findings and restoring the canonical
  JSON helper import path used by ASR and review modules.
- Focused regression set (`test_retranscribe_span.py`,
  `test_uncertainty_classifier.py`, `test_chunk_integrity.py`): 5 passed.
- Full application, ASR, and CI suites have not been established as green.

## Open gates

- The remaining addendum tasks are not verified by this progress record.
- The frozen <=5% normalized WER gate remains unchanged and has not been met by
  any newly evaluated configuration here.
- Real local inference, complete matched ablations, and independent clinical
  acceptance remain unverified or resource dependent.
