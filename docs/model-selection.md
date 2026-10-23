# Model selection status — 24 October 2026

## Why tiny.en is currently running

The developer provisioned tiny.en to test the local CPU pipeline with a small
checkpoint. There was no accuracy tournament, automatic model selector or
evidence that it was the best clinical model. Only tiny.en has measured results
so far: 16.42% normalized WER on six selected PriMock57 clips from one consultation.
That fails the user's required **≤3%** maximum. No production model is selected.
The synthetic demo reference text is separate from measured ASR output.

The local machine is an Intel i5-1135G7, four cores/eight threads, approximately
16 GB system RAM and Intel Iris Xe integrated graphics. Its current runtime uses
CPU INT8; it has no identified NVIDIA CUDA device. Exact model/runtime/quantization
combinations must be benchmarked rather than assuming published GPU results apply.

## Complete blueprint candidate list

These are planned candidates, not thirteen completed experiments.

| Candidate/configuration | Intended comparison | Measured here? |
| --- | --- | --- |
| Whisper large-v3 / faster-whisper | Large general-ASR control | Not yet; local artifact preparation started |
| Google MedASR, greedy | Medical dictation challenger | No |
| Google MedASR, approved external decoder | Decoder variant using the same weights | No |
| Eka Parrotlet-a-en-5b | Indian-English medical challenger | No |
| Eka Parrotlet-a-2.5-pro, English | Medical challenger | No |
| Omi Med STT v1 | Medical dialogue challenger | No |
| MultiMed Whisper-Small-English | Medical research checkpoint | No |
| Whisper-small | Matched general control for MultiMed | No |
| Distil-Whisper distil-large-v3 | Compact quality/latency control | No |
| NVIDIA Parakeet-TDT-0.6B-v2 | General control for Omi's parent architecture | No |
| NVIDIA Canary-Qwen-2.5B | Speech-language-model control | No |
| Amazon Transcribe Medical | Hosted medical comparator | No; authorized account/cost/disclosure required |
| Deepgram Nova-3 Medical | Hosted medical comparator | No; authorized account/cost/disclosure required |

Model IDs in the registry describe planned configurations; gated access, exact
artifacts, licenses and runtime adapters must be resolved for each before use.
For example, Google MedASR uses the Health AI Developer Foundations terms;
an unofficial site describing it as Apache-licensed must not override the
[official model card](https://huggingface.co/google/medasr).

## How a winner will be selected

Use the same frozen development recordings, references, normalization and failure
policy for all eligible models. Report aggregate and subgroup WER, per-recording
outliers, complete-source coverage, critical clinical errors, resource use and
clinician review effort. Keep related clips in the same corpus partition.
Advance eligible finalists to independent, representative, frozen acceptance
consultations. Do not keep tuning on that acceptance set.

The unrounded aggregate normalized WER must be ≤0.03, with no processing failures.
This is necessary but does not replace drug/dose/unit/allergy/negation adjudication,
licensing, deployment and clinical approval. If no candidate qualifies, report
that none qualifies and retain supervised development/manual review. Do not
relax normalization, discard hard clips, silently change models or label the
least-bad candidate as passing. No per-recording WER guarantee is possible
without a verified reference for that recording.
