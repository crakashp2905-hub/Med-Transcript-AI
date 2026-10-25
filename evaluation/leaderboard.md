# ASR benchmark ranking

Dataset: `primock57-consultation01-six-utterance-smoke-v1`

Manifest SHA-256: `0705189f86bb7ec51225e8b5c4fa10fd859f3fcf2295aa3219283c1ca79bbbfd`

Required normalized WER: **≤3%**. Lower is better. Equal exact scores share a rank.

| Rank | Model/configuration | Normalized WER | Failed clips | 3% gate |
| --- | --- | ---: | ---: | --- |
| 1 | parakeet-tdt-0.6b-v2 | 5.22% | 0 | fail |
| 2 | omi-med-stt-v1 | 6.72% | 0 | fail |
| 3 | faster-whisper-large-v3 | 7.46% | 0 | fail |
| 4 | distil-whisper-large-v3 | 9.70% | 0 | fail |
| 4 | whisper-small | 9.70% | 0 | fail |
| 6 | faster-whisper-tiny.en | 16.42% | 0 | fail |
| 7 | multimed-whisper-small-english | 41.04% | 2 | fail |

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

Six clips from one consultation; upstream references are not independently clinically adjudicated. No production winner from this screening set.

Paid calls are disabled. Blocked and untested models have no quality rank. Failed clips remain in measured runs' denominators. No production model is selected.
