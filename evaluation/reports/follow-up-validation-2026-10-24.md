# Follow-up validation of the two lowest-error screening configurations

30 clips from 5 additional consultation groups, 575 reference words.

Frozen manifest: `39e123830ba2dcff73b5621f1a4f10cbf76cd1eb8a7c56654c6d3d40e4cdbac7`.

Models, quantization and scoring were unchanged from screening. No reference edits or outcome-dependent exclusions.

| Model/configuration | Initial 6-clip WER | New 30-clip WER | Edits / words | Failures | 3% gate |
| --- | ---: | ---: | ---: | ---: | --- |
| omi-med-stt-v1 | 6.72% | 8.70% | 50/575 | 0 | fail |
| parakeet-tdt-0.6b-v2 | 5.22% | 13.91% | 80/575 | 0 | fail |

## Consultation groups

| Group | Model | Edits / words | Normalized WER |
| --- | --- | ---: | ---: |
| day1_consultation02 | omi-med-stt-v1 | 12/122 | 9.84% |
| day1_consultation03 | omi-med-stt-v1 | 9/120 | 7.50% |
| day1_consultation04 | omi-med-stt-v1 | 13/115 | 11.30% |
| day1_consultation05 | omi-med-stt-v1 | 7/99 | 7.07% |
| day1_consultation06 | omi-med-stt-v1 | 9/119 | 7.56% |
| day1_consultation02 | parakeet-tdt-0.6b-v2 | 19/122 | 15.57% |
| day1_consultation03 | parakeet-tdt-0.6b-v2 | 9/120 | 7.50% |
| day1_consultation04 | parakeet-tdt-0.6b-v2 | 24/115 | 20.87% |
| day1_consultation05 | parakeet-tdt-0.6b-v2 | 14/99 | 14.14% |
| day1_consultation06 | parakeet-tdt-0.6b-v2 | 14/119 | 11.76% |

## Speaker roles

| Group | Model | Edits / words | Normalized WER |
| --- | --- | ---: | ---: |
| doctor | omi-med-stt-v1 | 30/294 | 10.20% |
| patient | omi-med-stt-v1 | 20/281 | 7.12% |
| doctor | parakeet-tdt-0.6b-v2 | 48/294 | 16.33% |
| patient | parakeet-tdt-0.6b-v2 | 32/281 | 11.39% |

Only five consultation groups; speaker and training independence are unverified. No population-level confidence or clinical safety claim.

These are text-only offline benchmark adapters, not clinical transcript publishers. Full consultation, microphone, noise, overlap and clinician drug/dose/unit/negation validation remains pending. The application model was not switched by these runs.
