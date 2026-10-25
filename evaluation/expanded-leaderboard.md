# ASR benchmark ranking

Dataset: `primock57-20consultations-120clips-v1`

Manifest SHA-256: `d8945178c3ef0424745783c03675a5b37065682804fa60f06d33c08c5c3f2471`

Required normalized WER: **≤5%**. Lower is better. Equal exact scores share a rank.

| Rank | Model/configuration | Normalized WER | Failed clips | 5% gate |
| --- | --- | ---: | ---: | --- |
| 1 | omi-med-stt-v1 | 8.70% | 0 | fail |
| 2 | parakeet-tdt-0.6b-v2 | 13.25% | 0 | fail |
| 3 | distil-whisper-large-v3 | 15.72% | 0 | fail |
| 4 | faster-whisper-large-v3 | 16.56% | 0 | fail |
| 5 | whisper-small | 18.07% | 0 | fail |
| 6 | faster-whisper-tiny.en | 22.31% | 0 | fail |
| 7 | multimed-whisper-small-english | 42.05% | 0 | fail |

## Unranked candidates

| Candidate | Status | Reason |
| --- | --- | --- |
| google-medasr-greedy | access_pending | Google model gate requires user approval/login; no HF credentials configured. |
| google-medasr-approved-decoder | access_pending | Same gated MedASR weights and gated 6-gram decoder; no approved access. |
| eka-parrotlet-a-en-5b | access_pending | Hugging Face model gate requires user approval/login. |
| eka-parrotlet-a-2.5-pro-english | resource_preflight_blocked | Public BF16 weights total about 9.95 GB; reviewed canonical loader defaults to FP32 plus duplicate encoder loading, exceeding this 16 GB host physical RAM. No qualified CPU quantization provisioned. |
| canary-qwen-2.5b | resource_preflight_blocked | Dependency resolution succeeded. Reviewed NeMo 3.0 SALM initializes FP32; conservative weights + checkpoint + 2 GiB runtime allowance estimate is 17.50 GB versus 16.91 GB physical RAM. Inference not attempted; no qualified lower-memory CPU variant or NVIDIA GPU. |
| amazon-transcribe-medical | disabled_by_user | User authorized no paid calls; AWS credentials not configured. |
| deepgram-nova-3-medical | disabled_by_user | User authorized no paid calls; Deepgram credentials not configured. |

118 selected utterances from 20 new public mock consultation groups across five recording days; separate speaker tracks, predominantly clean speech. One role supplies only one untagged eligible utterance. Repeated speakers and model-training overlap are not ruled out. Text-only development comparison, not independent clinical acceptance. No production winner.

Paid calls are disabled. Blocked and untested models have no quality rank. Failed clips remain in measured runs' denominators. No production model is selected.
