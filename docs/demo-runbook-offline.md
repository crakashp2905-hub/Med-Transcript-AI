# Offline demonstration runbook

From the repository root, with the existing Python environment and cached web dependencies:

```powershell
.venv/Scripts/python.exe -m services.offline_preflight --out data/offline-preflight-v1.json
.venv/Scripts/python.exe -m services.offline_acceptance --version v2
.venv/Scripts/python.exe -m services.offline_demo
```

Use a new acceptance/preflight output version if a file already exists. Nothing installs dependencies, downloads model weights, requests paid APIs, activates Google or collects clinical data. `python -m services.engineering_status` reports the evidence-verified task count. Acceptance produces a versioned JSON report, `data/offline-acceptance-summary.json` and `docs/offline-acceptance-summary.md`.

The account-free demo binds `127.0.0.1:8010`, with isolated storage under `data/offline-demo-<UUID>`. Its `access.json` holds distinct local clinician and read-only viewer keys; keys are not printed or published. This is a local role/session simulator, not verified live OIDC. Existing Google simulation tests remain independently scoped.

The bundled workflow uses developer-scripted reference text and a silent PCM transport fixture. It is **not speech, ASR output or independent clinical gold**. Open the prepared synthetic encounter and inspect the deliberate warfarin dose mismatch, its blocked version, the corrected exact-version approval and the four hash-checked export formats. Programmatically set review flags exercise invariants; they are not human sign-offs.

For real-audio inspection use only the already provisioned licensed public mock examples; absent assets stay unavailable. Existing recorded benchmark hypotheses can be replayed with `python -m services.benchmark_integrity --out data/saved-metric-replay-v1.json`; this performs no inference.

Troubleshooting: missing npm dependencies or Python wheels are named blockers, not auto-installed. No model is required for the scripted route. No microphone is required for upload/manual-reference review. A full disk or write failure must be treated as failed storage; never claim recording was retained. Use a fresh isolated directory after interruption, and preserve failed reports. Physical recording, codecs and cached models require their own tests. Clinical release remains blocked even when every runnable check passes.
