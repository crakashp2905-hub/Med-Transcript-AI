# PriMock57 local dataset smoke test — 24 October 2026

The current local model is `Systran/faster-whisper-tiny.en`, revision
`0d3d19a32d3338f10357c0889762bd8d64bbdeba`, running through faster-whisper
1.2.1/CTranslate2 on CPU, INT8, four threads, beam size five, English forced.
VAD, previous-text conditioning and word timestamps are disabled. This is an
integration model, not an admitted clinical model.

## Dataset and preparation

[PriMock57](https://github.com/babylonhealth/primock57), by Alex Papadopoulos
Korfiatis, Francesco Moramarco, Radmila Sarac and Aleksandar Savkov (2022),
Babylon Health, is distributed under
[CC BY 4.0](https://github.com/babylonhealth/primock57/blob/cd2ac707ad03cb4d2531f4ec6b90c659bf4357c5/LICENSE.md).
It contains simulated consultations, not recordings of actual patient care.

Pinned dataset revision: `cd2ac707ad03cb4d2531f4ec6b90c659bf4357c5`.
Downloaded the doctor and patient tracks for `day1_consultation01` and verified
both against upstream Git LFS SHA-256 objects. Converted to mono 16 kHz PCM.
Before inference, selected the first three utterances per track lasting 4–20
seconds with at least five reference words and no uncertain/unintelligible tags.
Cropped them with 250 ms padding. This produces six clips from **one** consultation.
Source annotations, checksums, license, attribution, offsets and audio remain
under ignored `data/datasets/primock57-smoke/`.

## Observed results

| Measure | Result |
| --- | ---: |
| Clips | 6 |
| Reference words | 134 |
| Processing/timestamp failures | 0 |
| Normalized edit count | 22 |
| Normalized word error rate | 16.42% |
| Raw, case/punctuation-sensitive WER | 33.58% |

Normalization lowercases and tokenizes while preserving decimals, unit words and
negation. Fillers/repetitions remain in the reference, so their omission counts
as errors. For example, the model rendered `watery stool` as `watery stall`.
The standard API-equivalent output/timestamp validator passed all six clips.
Aggregate and per-clip counts are recorded in the accompanying JSON; full
references and hypotheses remain in the local ignored results file.

The patient track's first clip also passed the live API upload, durable ingest
and ASR worker workflow. Its encounter ID is
`699f6a88-0e7e-4d34-9cc2-aea47a7e34a2` in this workstation's development database.
The transcript remains unreviewed, without clinician approval or a generated
approved note. The original built-in demo still uses its explicitly labeled
reference transcript; it is separate from this measured dataset inference.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m services.prepare_primock
.\.venv\Scripts\python.exe -m services.evaluation --manifest data/datasets/primock57-smoke/manifest.json --profiles data/asr-smoke-profiles.json --profile-id tiny-en-smoke-v1 --out data/datasets/primock57-smoke/results-tiny-en.json --retain-hypotheses
```

Preparation explicitly downloads public dataset files; inference uses local
model files and audio. No audio was sent to a hosted transcription provider.
The local model profile must already exist with verified artifacts.

These selected short, separately recorded speaker clips do not test full
consultations, overlapping speech, diarization, other accents or drug/dose
accuracy. There are no independent consultation replicates, confidence intervals
or clinician adjudications. This development smoke test does not estimate
clinical accuracy, satisfy release gates or select a production engine.
