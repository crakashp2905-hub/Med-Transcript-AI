# Tested runtime matrix

This matrix lists only combinations with repository evidence. It is a record of tested scope, not a general support or clinical-use claim.

| Component | Tested combination | Evidence | Boundary |
| --- | --- | --- | --- |
| Python backend and local synthetic workflows | Windows 11 build `10.0.26200`; CPython `3.13.5` | Hash-bound reports identify this runtime across backend, recovery and workflow tests. | No second OS or production server configuration is covered. |
| Browser visual regression | Windows `win32`; Google Chrome `157.0.0.0`; Playwright `1.64.1`; headless; emulated viewports 1440×900, 1024×768 and 390×844 | `evaluation/reports/master-task-mta-09-20-4304b85.json` | Static investor-preview visual tests only. Viewports are emulations, not physical tablets or phones. |
| Audio-transform resource sample | Windows 11 build `10.0.26200`; CPython `3.13.5`; Intel64 Family 6 Model 140, 8 logical CPUs | `evaluation/reports/audio-filter-resource-v1.json` | Six short public clips, maximum 10.426 seconds; enhancement transforms only. RAM capacity, microphone/interface, ASR memory and longer real consultations were not measured. |
| TypeScript | `7.0.2` | `apps/clinician-web/package.json`; pinned frontend build | The version is pinned; the matrix does not imply compatibility with untested TypeScript versions. |
| Web toolchain inventory | Node `22.16.0`; npm `10.9.2`; Playwright package `1.64.1` | Local tool version output on 2026-11-14 | Versions are an inventory, not a cross-platform compatibility guarantee. |

## Not established

- Physical microphone or audio-interface compatibility; the user has not identified a device.
- Firefox, Safari, Edge, mobile browsers, or physical mobile/tablet devices.
- A clinically representative ASR workload meeting the unchanged 5% gate.
- Total-process memory or performance on devices other than the measured Intel Windows workstation.
- PostgreSQL, container, cloud, or institutional deployment compatibility.

Add a combination to the tested matrix only after its exact OS, device/browser or hardware, command, result and failure record are captured in a source-bound report. Missing hardware or assets stay unsupported.
