# Offline acceptance summary

Clinical release: `BLOCKED_EXTERNAL_EVIDENCE_REQUIRED`.

| Check | Status |
| --- | --- |
| backend_tests | fail |
| baseline_integrity | pass |
| saved_metrics_replay | pass |
| frontend_build | pass |
| synthetic_walkthrough | pass |
| source_integrity | pass |

Report: [offline-acceptance-v8.json](../evaluation/reports/offline-acceptance-v8.json)

Python sockets are restricted to loopback; this is not an operating-system firewall or native process sandbox.
Skipped checks, missing cached tools and unavailable independent evidence are not passes.
The scripted silent-audio workflow tests software invariants, not speech recognition or clinician performance.
