# Offline acceptance summary

Clinical release: `BLOCKED_EXTERNAL_EVIDENCE_REQUIRED`.

| Check | Status |
| --- | --- |
| backend_tests | fail |
| frontend_build | not_run |
| baseline_integrity | pass |
| saved_metrics_replay | pass |
| synthetic_walkthrough | pass |
| source_integrity | pass |

Report: [offline-acceptance-v20.json](../evaluation/reports/offline-acceptance-v20.json)

Python sockets are restricted to loopback; this is not an operating-system firewall or native process sandbox.
Skipped checks, missing cached tools and unavailable independent evidence are not passes.
The scripted silent-audio workflow tests software invariants, not speech recognition or clinician performance.
