# Model selection status — 24 October 2026

The current user requirement is **≤5% normalized WER**. The original screening and five-group follow-up below used the historical 3% gate. The expanded 120-clip comparison is predeclared in `evaluation/expanded-protocol-v1.json` and tests all seven local configurations uniformly as text-only recognizers. Access and resource blockers remain explicit; hosted calls remain disabled.

## Why tiny.en is currently running

The developer provisioned tiny.en to test the local CPU pipeline with a small
checkpoint. There was no accuracy tournament, automatic model selector or
evidence that it was the best clinical model. Initially, only tiny.en had measured
results: 16.42% normalized WER on six selected PriMock57 clips from one consultation.
Large-v3 has now also been measured on the identical manifest: **7.46%**, ten
edits across 134 reference words, no processing failures. Both fail the user's
required **≤3%** maximum. No production model is selected.
The later complete candidate audit and seven measured configurations are now in
the [screening leaderboard](../evaluation/leaderboard.md), generated from the
[frozen recorded dataset](../evaluation/datasets/primock57-smoke-v1/README.md).
The synthetic demo reference text is separate from measured ASR output.

The local machine is an Intel i5-1135G7, four cores/eight threads, approximately
16 GB system RAM and Intel Iris Xe integrated graphics. Its current runtime uses
CPU INT8; it has no identified NVIDIA CUDA device. Exact model/runtime/quantization
combinations must be benchmarked rather than assuming published GPU results apply.

## Complete blueprint candidate list

All thirteen candidates have explicit ledger entries. Six of them plus the
additional tiny.en integration fixture have measured screening results.

| Candidate/configuration | Intended comparison | Measured here? |
| --- | --- | --- |
| Whisper large-v3 / faster-whisper | Large general-ASR control | Six-clip smoke: 7.46%, fails 3% limit |
| Google MedASR, greedy | Medical dictation challenger | Access gate pending |
| Google MedASR, approved external decoder | Decoder variant using the same weights | Access gate pending |
| Eka Parrotlet-a-en-5b | Indian-English medical challenger | Access gate pending |
| Eka Parrotlet-a-2.5-pro, English | Medical challenger | Conservative host-memory preflight blocked; no inference |
| Omi Med STT v1 | Medical dialogue challenger | GGUF Q8 CPU: 6.72% |
| MultiMed Whisper-Small-English | Medical research checkpoint | Converted INT8 CPU: 41.04%, two failed clips |
| Whisper-small | Matched general control for MultiMed | INT8 CPU: 9.70% |
| Distil-Whisper distil-large-v3 | Compact quality/latency control | INT8 CPU: 9.70% |
| NVIDIA Parakeet-TDT-0.6B-v2 | General control for Omi's parent architecture | Third-party ONNX INT8 CPU export: 5.22% |
| NVIDIA Canary-Qwen-2.5B | Speech-language-model control | Dependency resolution passed; conservative memory preflight blocked |
| Amazon Transcribe Medical | Hosted medical comparator | User disabled paid calls |
| Deepgram Nova-3 Medical | Hosted medical comparator | User disabled paid calls |

Model IDs in the registry describe planned configurations; gated access, exact
artifacts, licenses and runtime adapters must be resolved for each before use.
For example, Google MedASR uses the Health AI Developer Foundations terms;
an unofficial site describing it as Apache-licensed must not override the
[official model card](https://huggingface.co/google/medasr).

The executed comparison, including model revisions and the shared manifest hash,
is in [the comparison report](../evaluation/reports/primock57-asr-comparison-2026-10-24.json).
The large-v3 model file matched upstream SHA-256 before inference. Runtime was
faster-whisper 1.2.1, CPU INT8, four threads, beam five, forced English. The app's
active model was left unchanged; a better smoke score does not establish approval.

The source-of-truth ranking has seven measured configurations and seven unranked
entries. Equal exact WERs share a rank. This is a ranking of these configurations
on this dataset, not a universal ranking of their model families. All fourteen
entries include the thirteen requested candidates and the extra tiny.en control.
See the [resource preflight](../evaluation/resource-preflight.json) for allocation
assumptions. Memory admission decisions are estimates, not observed inference
failures or claims that a model cannot run with any other implementation.

Omi and ONNX Parakeet use text-only benchmark adapters: they are not admitted
clinical transcript publishers and do not provide validated source timestamps.
Whisper-family runs retain API-equivalent output/timestamp validation; two
MultiMed outputs were rejected and counted as reference-word deletions under the
declared failure policy. Its 41.04% is this pipeline's failure-inclusive result,
not a raw-text-only WER claim. Do not equate the score to standalone model quality.
Reported elapsed times include loading and some runs overlapped; latency was not
used for ranking. All configurations still require independent clinical review.

## How a winner will be selected

Use the same frozen development recordings, references, normalization and failure
policy for all eligible models. Report aggregate and subgroup WER, per-recording
outliers, complete-source coverage, critical clinical errors, resource use and
clinician review effort. Keep related clips in the same corpus partition.
Advance eligible finalists to independent, representative, frozen acceptance
consultations. Do not keep tuning on that acceptance set.

The unrounded aggregate normalized WER must now be ≤0.05, with no processing failures.
This is necessary but does not replace drug/dose/unit/allergy/negation adjudication,
licensing, deployment and clinical approval. If no candidate qualifies, report
that none qualifies and retain supervised development/manual review. Do not
relax normalization, discard hard clips, silently change models or label the
least-bad candidate as passing. No per-recording WER guarantee is possible
without a verified reference for that recording.
