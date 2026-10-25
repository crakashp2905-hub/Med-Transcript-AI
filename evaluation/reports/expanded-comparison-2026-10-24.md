# Expanded local ASR comparison

118 fixed clips; 20 new consultation groups; 2264 reference words. Required normalized WER: **≤5%**.

All seven local configurations use text-only adapters. References, scorer, failure policy and model artifacts were fixed before inference. No paid calls.

[Preserved Omi first attempt and Windows loader repair](expanded-omi-runtime-repair-2026-10-24.md). The final comparison uses its complete repaired rerun, not selected successful clips.

| Rank | Model/configuration | Normalized WER | Edits / words | Failed clips | 5% gate |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | omi-med-stt-v1 | 8.70% | 197/2264 | 0 | fail |
| 2 | parakeet-tdt-0.6b-v2 | 13.25% | 300/2264 | 0 | fail |
| 3 | distil-whisper-large-v3 | 15.72% | 356/2264 | 0 | fail |
| 4 | faster-whisper-large-v3 | 16.56% | 375/2264 | 0 | fail |
| 5 | whisper-small | 18.07% | 409/2264 | 0 | fail |
| 6 | faster-whisper-tiny.en | 22.31% | 505/2264 | 0 | fail |
| 7 | multimed-whisper-small-english | 42.05% | 952/2264 | 0 | fail |

## Recording days

| Group | Model | Edits / words | Normalized WER | Failed clips |
| --- | --- | ---: | ---: | ---: |
| day1 | omi-med-stt-v1 | 40/426 | 9.39% | 0 |
| day2 | omi-med-stt-v1 | 54/499 | 10.82% | 0 |
| day3 | omi-med-stt-v1 | 44/471 | 9.34% | 0 |
| day4 | omi-med-stt-v1 | 36/400 | 9.00% | 0 |
| day5 | omi-med-stt-v1 | 23/468 | 4.91% | 0 |
| day1 | parakeet-tdt-0.6b-v2 | 82/426 | 19.25% | 0 |
| day2 | parakeet-tdt-0.6b-v2 | 60/499 | 12.02% | 0 |
| day3 | parakeet-tdt-0.6b-v2 | 75/471 | 15.92% | 0 |
| day4 | parakeet-tdt-0.6b-v2 | 40/400 | 10.00% | 0 |
| day5 | parakeet-tdt-0.6b-v2 | 43/468 | 9.19% | 0 |
| day1 | distil-whisper-large-v3 | 76/426 | 17.84% | 0 |
| day2 | distil-whisper-large-v3 | 89/499 | 17.84% | 0 |
| day3 | distil-whisper-large-v3 | 77/471 | 16.35% | 0 |
| day4 | distil-whisper-large-v3 | 58/400 | 14.50% | 0 |
| day5 | distil-whisper-large-v3 | 56/468 | 11.97% | 0 |
| day1 | faster-whisper-large-v3 | 78/426 | 18.31% | 0 |
| day2 | faster-whisper-large-v3 | 98/499 | 19.64% | 0 |
| day3 | faster-whisper-large-v3 | 89/471 | 18.90% | 0 |
| day4 | faster-whisper-large-v3 | 61/400 | 15.25% | 0 |
| day5 | faster-whisper-large-v3 | 49/468 | 10.47% | 0 |
| day1 | whisper-small | 103/426 | 24.18% | 0 |
| day2 | whisper-small | 95/499 | 19.04% | 0 |
| day3 | whisper-small | 87/471 | 18.47% | 0 |
| day4 | whisper-small | 69/400 | 17.25% | 0 |
| day5 | whisper-small | 55/468 | 11.75% | 0 |
| day1 | faster-whisper-tiny.en | 121/426 | 28.40% | 0 |
| day2 | faster-whisper-tiny.en | 129/499 | 25.85% | 0 |
| day3 | faster-whisper-tiny.en | 86/471 | 18.26% | 0 |
| day4 | faster-whisper-tiny.en | 76/400 | 19.00% | 0 |
| day5 | faster-whisper-tiny.en | 93/468 | 19.87% | 0 |
| day1 | multimed-whisper-small-english | 290/426 | 68.08% | 0 |
| day2 | multimed-whisper-small-english | 274/499 | 54.91% | 0 |
| day3 | multimed-whisper-small-english | 103/471 | 21.87% | 0 |
| day4 | multimed-whisper-small-english | 92/400 | 23.00% | 0 |
| day5 | multimed-whisper-small-english | 193/468 | 41.24% | 0 |

## Speaker roles

| Group | Model | Edits / words | Normalized WER | Failed clips |
| --- | --- | ---: | ---: | ---: |
| doctor | omi-med-stt-v1 | 50/1137 | 4.40% | 0 |
| patient | omi-med-stt-v1 | 147/1127 | 13.04% | 0 |
| doctor | parakeet-tdt-0.6b-v2 | 118/1137 | 10.38% | 0 |
| patient | parakeet-tdt-0.6b-v2 | 182/1127 | 16.15% | 0 |
| doctor | distil-whisper-large-v3 | 133/1137 | 11.70% | 0 |
| patient | distil-whisper-large-v3 | 223/1127 | 19.79% | 0 |
| doctor | faster-whisper-large-v3 | 131/1137 | 11.52% | 0 |
| patient | faster-whisper-large-v3 | 244/1127 | 21.65% | 0 |
| doctor | whisper-small | 157/1137 | 13.81% | 0 |
| patient | whisper-small | 252/1127 | 22.36% | 0 |
| doctor | faster-whisper-tiny.en | 214/1137 | 18.82% | 0 |
| patient | faster-whisper-tiny.en | 291/1127 | 25.82% | 0 |
| doctor | multimed-whisper-small-english | 191/1137 | 16.80% | 0 |
| patient | multimed-whisper-small-english | 761/1127 | 67.52% | 0 |

## Consultations

| Group | Model | Edits / words | Normalized WER | Failed clips |
| --- | --- | ---: | ---: | ---: |
| day1_consultation07 | omi-med-stt-v1 | 15/132 | 11.36% | 0 |
| day1_consultation08 | omi-med-stt-v1 | 7/78 | 8.97% | 0 |
| day1_consultation09 | omi-med-stt-v1 | 6/109 | 5.50% | 0 |
| day1_consultation10 | omi-med-stt-v1 | 12/107 | 11.21% | 0 |
| day2_consultation01 | omi-med-stt-v1 | 11/151 | 7.28% | 0 |
| day2_consultation02 | omi-med-stt-v1 | 24/145 | 16.55% | 0 |
| day2_consultation03 | omi-med-stt-v1 | 10/100 | 10.00% | 0 |
| day2_consultation04 | omi-med-stt-v1 | 9/103 | 8.74% | 0 |
| day3_consultation01 | omi-med-stt-v1 | 10/99 | 10.10% | 0 |
| day3_consultation02 | omi-med-stt-v1 | 15/130 | 11.54% | 0 |
| day3_consultation03 | omi-med-stt-v1 | 10/125 | 8.00% | 0 |
| day3_consultation04 | omi-med-stt-v1 | 9/117 | 7.69% | 0 |
| day4_consultation01 | omi-med-stt-v1 | 14/83 | 16.87% | 0 |
| day4_consultation02 | omi-med-stt-v1 | 1/95 | 1.05% | 0 |
| day4_consultation03 | omi-med-stt-v1 | 12/115 | 10.43% | 0 |
| day4_consultation04 | omi-med-stt-v1 | 9/107 | 8.41% | 0 |
| day5_consultation01 | omi-med-stt-v1 | 6/129 | 4.65% | 0 |
| day5_consultation02 | omi-med-stt-v1 | 2/91 | 2.20% | 0 |
| day5_consultation03 | omi-med-stt-v1 | 8/156 | 5.13% | 0 |
| day5_consultation04 | omi-med-stt-v1 | 7/92 | 7.61% | 0 |
| day1_consultation07 | parakeet-tdt-0.6b-v2 | 26/132 | 19.70% | 0 |
| day1_consultation08 | parakeet-tdt-0.6b-v2 | 11/78 | 14.10% | 0 |
| day1_consultation09 | parakeet-tdt-0.6b-v2 | 25/109 | 22.94% | 0 |
| day1_consultation10 | parakeet-tdt-0.6b-v2 | 20/107 | 18.69% | 0 |
| day2_consultation01 | parakeet-tdt-0.6b-v2 | 10/151 | 6.62% | 0 |
| day2_consultation02 | parakeet-tdt-0.6b-v2 | 22/145 | 15.17% | 0 |
| day2_consultation03 | parakeet-tdt-0.6b-v2 | 15/100 | 15.00% | 0 |
| day2_consultation04 | parakeet-tdt-0.6b-v2 | 13/103 | 12.62% | 0 |
| day3_consultation01 | parakeet-tdt-0.6b-v2 | 17/99 | 17.17% | 0 |
| day3_consultation02 | parakeet-tdt-0.6b-v2 | 26/130 | 20.00% | 0 |
| day3_consultation03 | parakeet-tdt-0.6b-v2 | 14/125 | 11.20% | 0 |
| day3_consultation04 | parakeet-tdt-0.6b-v2 | 18/117 | 15.38% | 0 |
| day4_consultation01 | parakeet-tdt-0.6b-v2 | 6/83 | 7.23% | 0 |
| day4_consultation02 | parakeet-tdt-0.6b-v2 | 7/95 | 7.37% | 0 |
| day4_consultation03 | parakeet-tdt-0.6b-v2 | 15/115 | 13.04% | 0 |
| day4_consultation04 | parakeet-tdt-0.6b-v2 | 12/107 | 11.21% | 0 |
| day5_consultation01 | parakeet-tdt-0.6b-v2 | 13/129 | 10.08% | 0 |
| day5_consultation02 | parakeet-tdt-0.6b-v2 | 7/91 | 7.69% | 0 |
| day5_consultation03 | parakeet-tdt-0.6b-v2 | 14/156 | 8.97% | 0 |
| day5_consultation04 | parakeet-tdt-0.6b-v2 | 9/92 | 9.78% | 0 |
| day1_consultation07 | distil-whisper-large-v3 | 25/132 | 18.94% | 0 |
| day1_consultation08 | distil-whisper-large-v3 | 11/78 | 14.10% | 0 |
| day1_consultation09 | distil-whisper-large-v3 | 23/109 | 21.10% | 0 |
| day1_consultation10 | distil-whisper-large-v3 | 17/107 | 15.89% | 0 |
| day2_consultation01 | distil-whisper-large-v3 | 20/151 | 13.25% | 0 |
| day2_consultation02 | distil-whisper-large-v3 | 30/145 | 20.69% | 0 |
| day2_consultation03 | distil-whisper-large-v3 | 23/100 | 23.00% | 0 |
| day2_consultation04 | distil-whisper-large-v3 | 16/103 | 15.53% | 0 |
| day3_consultation01 | distil-whisper-large-v3 | 12/99 | 12.12% | 0 |
| day3_consultation02 | distil-whisper-large-v3 | 32/130 | 24.62% | 0 |
| day3_consultation03 | distil-whisper-large-v3 | 15/125 | 12.00% | 0 |
| day3_consultation04 | distil-whisper-large-v3 | 18/117 | 15.38% | 0 |
| day4_consultation01 | distil-whisper-large-v3 | 16/83 | 19.28% | 0 |
| day4_consultation02 | distil-whisper-large-v3 | 10/95 | 10.53% | 0 |
| day4_consultation03 | distil-whisper-large-v3 | 18/115 | 15.65% | 0 |
| day4_consultation04 | distil-whisper-large-v3 | 14/107 | 13.08% | 0 |
| day5_consultation01 | distil-whisper-large-v3 | 17/129 | 13.18% | 0 |
| day5_consultation02 | distil-whisper-large-v3 | 7/91 | 7.69% | 0 |
| day5_consultation03 | distil-whisper-large-v3 | 15/156 | 9.62% | 0 |
| day5_consultation04 | distil-whisper-large-v3 | 17/92 | 18.48% | 0 |
| day1_consultation07 | faster-whisper-large-v3 | 29/132 | 21.97% | 0 |
| day1_consultation08 | faster-whisper-large-v3 | 10/78 | 12.82% | 0 |
| day1_consultation09 | faster-whisper-large-v3 | 21/109 | 19.27% | 0 |
| day1_consultation10 | faster-whisper-large-v3 | 18/107 | 16.82% | 0 |
| day2_consultation01 | faster-whisper-large-v3 | 24/151 | 15.89% | 0 |
| day2_consultation02 | faster-whisper-large-v3 | 35/145 | 24.14% | 0 |
| day2_consultation03 | faster-whisper-large-v3 | 24/100 | 24.00% | 0 |
| day2_consultation04 | faster-whisper-large-v3 | 15/103 | 14.56% | 0 |
| day3_consultation01 | faster-whisper-large-v3 | 18/99 | 18.18% | 0 |
| day3_consultation02 | faster-whisper-large-v3 | 36/130 | 27.69% | 0 |
| day3_consultation03 | faster-whisper-large-v3 | 14/125 | 11.20% | 0 |
| day3_consultation04 | faster-whisper-large-v3 | 21/117 | 17.95% | 0 |
| day4_consultation01 | faster-whisper-large-v3 | 20/83 | 24.10% | 0 |
| day4_consultation02 | faster-whisper-large-v3 | 8/95 | 8.42% | 0 |
| day4_consultation03 | faster-whisper-large-v3 | 19/115 | 16.52% | 0 |
| day4_consultation04 | faster-whisper-large-v3 | 14/107 | 13.08% | 0 |
| day5_consultation01 | faster-whisper-large-v3 | 13/129 | 10.08% | 0 |
| day5_consultation02 | faster-whisper-large-v3 | 6/91 | 6.59% | 0 |
| day5_consultation03 | faster-whisper-large-v3 | 13/156 | 8.33% | 0 |
| day5_consultation04 | faster-whisper-large-v3 | 17/92 | 18.48% | 0 |
| day1_consultation07 | whisper-small | 33/132 | 25.00% | 0 |
| day1_consultation08 | whisper-small | 14/78 | 17.95% | 0 |
| day1_consultation09 | whisper-small | 32/109 | 29.36% | 0 |
| day1_consultation10 | whisper-small | 24/107 | 22.43% | 0 |
| day2_consultation01 | whisper-small | 19/151 | 12.58% | 0 |
| day2_consultation02 | whisper-small | 33/145 | 22.76% | 0 |
| day2_consultation03 | whisper-small | 25/100 | 25.00% | 0 |
| day2_consultation04 | whisper-small | 18/103 | 17.48% | 0 |
| day3_consultation01 | whisper-small | 11/99 | 11.11% | 0 |
| day3_consultation02 | whisper-small | 33/130 | 25.38% | 0 |
| day3_consultation03 | whisper-small | 19/125 | 15.20% | 0 |
| day3_consultation04 | whisper-small | 24/117 | 20.51% | 0 |
| day4_consultation01 | whisper-small | 22/83 | 26.51% | 0 |
| day4_consultation02 | whisper-small | 10/95 | 10.53% | 0 |
| day4_consultation03 | whisper-small | 22/115 | 19.13% | 0 |
| day4_consultation04 | whisper-small | 15/107 | 14.02% | 0 |
| day5_consultation01 | whisper-small | 23/129 | 17.83% | 0 |
| day5_consultation02 | whisper-small | 6/91 | 6.59% | 0 |
| day5_consultation03 | whisper-small | 12/156 | 7.69% | 0 |
| day5_consultation04 | whisper-small | 14/92 | 15.22% | 0 |
| day1_consultation07 | faster-whisper-tiny.en | 33/132 | 25.00% | 0 |
| day1_consultation08 | faster-whisper-tiny.en | 19/78 | 24.36% | 0 |
| day1_consultation09 | faster-whisper-tiny.en | 41/109 | 37.61% | 0 |
| day1_consultation10 | faster-whisper-tiny.en | 28/107 | 26.17% | 0 |
| day2_consultation01 | faster-whisper-tiny.en | 29/151 | 19.21% | 0 |
| day2_consultation02 | faster-whisper-tiny.en | 43/145 | 29.66% | 0 |
| day2_consultation03 | faster-whisper-tiny.en | 38/100 | 38.00% | 0 |
| day2_consultation04 | faster-whisper-tiny.en | 19/103 | 18.45% | 0 |
| day3_consultation01 | faster-whisper-tiny.en | 10/99 | 10.10% | 0 |
| day3_consultation02 | faster-whisper-tiny.en | 31/130 | 23.85% | 0 |
| day3_consultation03 | faster-whisper-tiny.en | 15/125 | 12.00% | 0 |
| day3_consultation04 | faster-whisper-tiny.en | 30/117 | 25.64% | 0 |
| day4_consultation01 | faster-whisper-tiny.en | 22/83 | 26.51% | 0 |
| day4_consultation02 | faster-whisper-tiny.en | 10/95 | 10.53% | 0 |
| day4_consultation03 | faster-whisper-tiny.en | 21/115 | 18.26% | 0 |
| day4_consultation04 | faster-whisper-tiny.en | 23/107 | 21.50% | 0 |
| day5_consultation01 | faster-whisper-tiny.en | 30/129 | 23.26% | 0 |
| day5_consultation02 | faster-whisper-tiny.en | 13/91 | 14.29% | 0 |
| day5_consultation03 | faster-whisper-tiny.en | 26/156 | 16.67% | 0 |
| day5_consultation04 | faster-whisper-tiny.en | 24/92 | 26.09% | 0 |
| day1_consultation07 | multimed-whisper-small-english | 32/132 | 24.24% | 0 |
| day1_consultation08 | multimed-whisper-small-english | 17/78 | 21.79% | 0 |
| day1_consultation09 | multimed-whisper-small-english | 28/109 | 25.69% | 0 |
| day1_consultation10 | multimed-whisper-small-english | 213/107 | 199.07% | 0 |
| day2_consultation01 | multimed-whisper-small-english | 48/151 | 31.79% | 0 |
| day2_consultation02 | multimed-whisper-small-english | 183/145 | 126.21% | 0 |
| day2_consultation03 | multimed-whisper-small-english | 24/100 | 24.00% | 0 |
| day2_consultation04 | multimed-whisper-small-english | 19/103 | 18.45% | 0 |
| day3_consultation01 | multimed-whisper-small-english | 21/99 | 21.21% | 0 |
| day3_consultation02 | multimed-whisper-small-english | 34/130 | 26.15% | 0 |
| day3_consultation03 | multimed-whisper-small-english | 18/125 | 14.40% | 0 |
| day3_consultation04 | multimed-whisper-small-english | 30/117 | 25.64% | 0 |
| day4_consultation01 | multimed-whisper-small-english | 38/83 | 45.78% | 0 |
| day4_consultation02 | multimed-whisper-small-english | 9/95 | 9.47% | 0 |
| day4_consultation03 | multimed-whisper-small-english | 28/115 | 24.35% | 0 |
| day4_consultation04 | multimed-whisper-small-english | 17/107 | 15.89% | 0 |
| day5_consultation01 | multimed-whisper-small-english | 25/129 | 19.38% | 0 |
| day5_consultation02 | multimed-whisper-small-english | 8/91 | 8.79% | 0 |
| day5_consultation03 | multimed-whisper-small-english | 137/156 | 87.82% | 0 |
| day5_consultation04 | multimed-whisper-small-english | 23/92 | 25.00% | 0 |

118 selected utterances from 20 new public mock consultation groups across five recording days; separate speaker tracks, predominantly clean speech. One role supplies only one untagged eligible utterance. Repeated speakers and model-training overlap are not ruled out. Text-only development comparison, not independent clinical acceptance. No production winner.

Text-only accuracy does not establish valid clinical timestamps or safe drug/dose/unit/negation handling. Clinical adjudication remains pending. The application's active model was not changed. Concurrent CPU timings are not a capacity benchmark.
