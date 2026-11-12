# Offline energy VAD chunking experiment

`services/asr/energy_vad_chunking.py` provides a deterministic energy-gated
boundary experiment for signed 16-bit mono PCM. It returns start-inclusive,
end-exclusive sample offsets, shifts a nominal 30-second boundary toward a
qualifying low-energy run, retains two seconds of context, and checks that the
chunks overlap or touch from the beginning through the final source sample.

This is an energy VAD proxy, not a trained VAD model. It does not identify
speech reliably in noise, music, quiet speech, or multi-speaker overlap. No VAD
package or model weights are available in the permitted local environment, so
the helper is not wired into production inference and no ASR quality claim is
made for its segmentation.

## Existing full ASR experiment

The independently saved full-corpus Faster Whisper large-v3 runs compare fixed
and overlapping windows on the same 16 cases (eight clean and eight distracted
recordings), each with 13,683 reference words per condition. These runs are
bound to `evaluation/detailed-suite-v4.json`; their source and report hashes
are pinned by `tests/test_detailed_benchmark.py`.

| Mode | Clean WER | Distracted WER | Failed cases |
| --- | ---: | ---: | ---: |
| Fixed | 20.69% (2,831/13,683) | 21.68% (2,967/13,683) | 0/16 |
| 2-second overlap | 23.59% (3,228/13,683) | 24.16% (3,306/13,683) | 0/16 |

Both modes preserve full input coverage and exceed the unchanged 5% admission
gate. The measured overlap mode worsens WER by 2.90 and 2.48 percentage points,
respectively. The new energy proxy has only synthetic unit-test evidence and
must not be inferred to improve these ASR results. ASR timestamps remain the
model's native timestamps, not chunk boundaries.

## Local checks

```powershell
python -m pytest -q tests/test_energy_vad_chunking.py tests/test_detailed_benchmark.py
python -m ruff check services/asr/energy_vad_chunking.py tests/test_energy_vad_chunking.py
python -m ruff format --check services/asr/energy_vad_chunking.py tests/test_energy_vad_chunking.py
```
