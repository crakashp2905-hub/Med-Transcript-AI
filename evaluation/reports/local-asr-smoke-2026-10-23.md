# Local ASR synthetic smoke — 23 October 2026

Outcome: the real local adapter completed upload → ingest → ASR → immutable
transcript retrieval on a generated English fixture. This was a software smoke
test, not clinical benchmarking, an ASR model selection, or release validation.

## Input and configuration

- Fixture: Windows Microsoft Zira Desktop speech synthesis, mono 16 kHz,
  signed 16-bit PCM WAV, 116,160 frames, 7,260 ms, 232,366 bytes.
- Expected phrase: “This is a synthetic recording for a transcription software
  test. No patient information is included.” No patient material was used.
- Original audio SHA-256: `f6beceb1c44fa9c5cea2374196f2d813c5c12d54940d67b77b96d31baafc7611`.
- Smoke-only checkpoint: `Systran/faster-whisper-tiny.en`, fixed revision
  `0d3d19a32d3338f10357c0889762bd8d64bbdeba`; public publisher metadata lists MIT.
- Runtime: Python 3.13.5 on Windows, faster-whisper 1.2.1, CTranslate2 4.8.3,
  CPU int8, four CPU threads, beam size five, temperature zero, English forced,
  VAD disabled, no word timestamps, no previous-text conditioning.
- Dependency snapshot: [tested environment](../../requirements/asr-windows-py313.lock.txt).
  Model files and audio remain in ignored local development storage.

## Observations

The worker published two segments:

| Original interval | Recognized text, with leading model whitespace omitted here |
|---|---|
| 0–4,000 ms | This is a synthetic recording for a transcription software test. |
| 4,000–7,000 ms | No patient information is included. |

The final 260 ms remained an untranscribed interval with unknown cause. The
saved transcript retained original segment whitespace and raw model timing.
It remained `review_required`, with language support and clinical coverage
unverified. No speaker role, diagnosis or clinical note was inferred.

A second real inference run succeeded with Python `socket.connect` and external
DNS calls guarded against non-loopback destinations; zero blocked connection
attempts were recorded. This checks the exercised Python networking path only.
It is not an operating-system firewall, a native-code network audit, or proof
that every dependency/configuration is offline-safe.

The guard is retained as a reproducible development helper:

```powershell
python -m tests.offline_smoke --synthetic-audio data/synthetic-asr-smoke.wav --asr-profiles data/asr-smoke-profiles.json
```

The referenced fixture/profile are ignored local files; provision your own
synthetic equivalents when reproducing this run on another workstation.

The base and isolated-environment regression suites passed, and the optional
ASR dependencies passed `pip check`. Unit tests use synthetic adapters/stubbed
engine objects to exercise failure and authorization boundaries without model
downloads. The smoke above separately exercised actual model inference.

No representative clinic corpus, ambient conversation, accent evaluation,
drug/dose/negation error analysis, clinical review-time study, latency percentile,
GPU test, diarization, large-v3 baseline or challenger comparison was performed.
The production model registry remains unselected. Matching one generated phrase
does not establish clinical performance.

Sources for artifact identity and interface:
[publisher checkpoint](https://huggingface.co/Systran/faster-whisper-tiny.en/tree/0d3d19a32d3338f10357c0889762bd8d64bbdeba),
[pinned runtime source](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py).
