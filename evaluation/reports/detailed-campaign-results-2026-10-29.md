# Detailed campaign execution results

All baseline comparisons complete: **True**. The 5% gate is unchanged. No model is promoted.

| Rank | Candidate | Clean WER | Distracted WER | Failed clean cases | Native timestamp bounds valid |
| --- | --- | --- | --- | --- | --- |
| 1 | omi-med-stt-v1-native-empty | 16.41% | 17.22% | 0 | False |
| 2 | faster-whisper-large-v3 | 20.69% | 21.68% | 0 | False |
| 3 | parakeet-tdt-0.6b-v2 | 21.82% | 22.55% | 0 | False |
| 4 | distil-whisper-large-v3 | 22.85% | 23.47% | 0 | False |
| 5 | whisper-small | 25.41% | 29.01% | 0 | False |
| 6 | qwen3-asr-0.6b-int8 | 26.18% | 28.06% | 0 | False |
| 7 | omi-med-stt-v1 | 27.84% | 28.50% | 1 | False |
| 8 | faster-whisper-tiny.en | 32.27% | 34.27% | 0 | False |
| 9 | multimed-whisper-small-english | 53.21% | 51.11% | 0 | False |

Unranked or interrupted candidates remain in the JSON receipt; no WER is invented. See each native timestamp report and failure-inclusive condition summary.

## Completed chunking conditions

| Candidate | Mode | Clean WER | Distracted WER |
| --- | --- | --- | --- |
| faster-whisper-large-v3 | overlap | 23.59% | 24.16% |
| omi-med-stt-v1-native-empty | overlap | 19.01% | 19.62% |
| omi-med-stt-v1-native-empty | speech_aware | 18.08% | 18.75% |

## Reference-note preservation screen

| Mode | Exact cases | Failed cases |
| --- | --- | --- |
| deterministic | 8/8 | 0 |
| qwen2.5:1.5b | 3/8 | 2 |
| qwen2.5:7b | 0/8 | 8 |

This is preservation of supplied source-note fixture units, not clinical note accuracy or clinician correction time. Independent annotation, physical recording observations and institutional approval remain unperformed.
