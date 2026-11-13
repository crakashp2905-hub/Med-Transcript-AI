# ASR compute measurement protocol

`evaluation/detailed-suite-v7.json` binds the benchmark runner's current source and the existing frozen MedDistract manifest. It disables historical output reuse so every full run measures the candidate against the same case cohort.

Each candidate report records per-case wall time, allowing the compute Pareto report to derive p50 and p95. It also records process CPU seconds from immediately before model load through model close and the operating system's process high-water resident set. The CPU and memory values are process-level measurements, not per-request attribution. A resumed run, if introduced in a future suite, must not be described as full-cohort resource measurement.

All listed candidates are local. Inference cost is therefore USD 0; no hosted or paid requests are allowed. The current environment lacks `faster-whisper`, `ctranslate2`, and `onnx_asr`, so no v7 candidate inference was run here. Existing saved WER and latency results remain preserved as historical evidence; they do not receive fabricated CPU or memory values.

Example command for a candidate after its pinned local runtime is present:

```powershell
python -m services.detailed_benchmark --suite evaluation/detailed-suite-v7.json --candidate faster-whisper-large-v3 --mode fixed --output evaluation/runs/meddistract-detailed-v7/faster-whisper-large-v3.fixed.json
```
