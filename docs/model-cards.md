# Machine-generated model cards

`python -m services.model_cards` is report-only: it reads the committed model
registry and benchmark reports, never downloads weights or runs inference. Cards
retain language, runtime/decoding settings, sample and reference counts,
normalized WER, failed samples, timeout counts, per-role metrics and explicit
limitations matching the [canonical product limits](clinical-limitations.md).
Candidates without a report remain visible as unavailable. The
immutable maximum normalized WER gate is 5%; no card authorizes clinical use.

- English-only, general-medicine documentation assistance.
- Synthetic/public-mock development evidence is not independent clinician gold; clinical validation is pending.
- The frozen 5% normalized-WER ASR gate remains unmet.
- Clinician review is required. The system does not diagnose or prescribe, and real-patient release is not authorized.
