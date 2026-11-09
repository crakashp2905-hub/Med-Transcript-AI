# Runtime support matrix

This project uses a deliberately small, explicit support envelope. A pinned
dependency is a tested point, not a claim that every future version is safe.

| Component | Minimum supported | Tested maximum / pinned point | Evidence |
| --- | --- | --- | --- |
| Python | 3.11 | 3.13.x (Windows development and CI) | `pyproject.toml`, `constraints-ci.txt` |
| Node.js | 22 | 24.x CI action lane; Node 22 frontend runbook | `docs/runbooks/ci.md`, `apps/clinician-web/package-lock.json` |
| TypeScript | package-pinned 7.0.2 | 7.0.2 | `apps/clinician-web/package.json` |
| PostgreSQL | 17 (only tested image) | 17 Compose image and hosted integration | `compose.yaml`, `docs/runbooks/ci.md` |
| Browser | Chrome/Edge with MediaRecorder | tested Windows Chrome/Edge path | `README.md`, browser receipts |

The Python constraints file records the exact installed development snapshot;
optional ASR, media, security and PostgreSQL extras remain separately gated.
Missing local runtimes are reported by offline preflight rather than installed
automatically. PostgreSQL and container execution remain externally hosted or
operator-provisioned checks when unavailable on the workstation.
