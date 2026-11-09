# Machine-generated model cards

`python -m services.model_cards` is report-only: it reads the committed model
registry and benchmark reports, never downloads weights or runs inference. Cards
retain language, runtime/decoding settings, sample and reference counts,
normalized WER, failed samples, timeout counts, per-role metrics and explicit
limitations. Candidates without a report remain visible as unavailable. The
immutable maximum normalized WER gate is 5%; no card authorizes clinical use.
