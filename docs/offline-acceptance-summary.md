# Offline acceptance summary

Clinical release: `BLOCKED_EXTERNAL_EVIDENCE_REQUIRED`.

| Check | Status |
| --- | --- |
| backend_tests | fail |
| source_integrity | fail |
| baseline_integrity | pass |
| saved_metrics_replay | pass |
| frontend_build | pass |
| synthetic_walkthrough | pass |
| clinical_binding_development | pass |

Report: [offline-acceptance-master-2026-11-14-7378243.json](../evaluation/reports/offline-acceptance-master-2026-11-14-7378243.json)

Python sockets are restricted to loopback; this is not an operating-system firewall or native process sandbox.
Skipped checks, missing cached tools and unavailable independent evidence are not passes.
The scripted silent-audio workflow tests software invariants, not speech recognition or clinician performance.
