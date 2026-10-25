# ASR benchmark ranking

Dataset: `primock57-consultations02-06-validation-v1`

Manifest SHA-256: `39e123830ba2dcff73b5621f1a4f10cbf76cd1eb8a7c56654c6d3d40e4cdbac7`

Required normalized WER: **≤3%**. Lower is better. Equal exact scores share a rank.

| Rank | Model/configuration | Normalized WER | Failed clips | 3% gate |
| --- | --- | ---: | ---: | --- |
| 1 | omi-med-stt-v1 | 8.70% | 0 | fail |
| 2 | parakeet-tdt-0.6b-v2 | 13.91% | 0 | fail |

## Unranked candidates

| Candidate | Status | Reason |
| --- | --- | --- |

30 preselected utterances from five additional public mock consultations; separate speaker tracks; repeated speakers and training overlap are not ruled out. Development validation only; no clinical acceptance or production winner.

Paid calls are disabled. Blocked and untested models have no quality rank. Failed clips remain in measured runs' denominators. No production model is selected.
