# Deterministic test environments

Python dependencies are installed from `constraints-ci.txt` under Python 3.13
in CI and the Windows runbook; frontend dependencies use the committed
`package-lock.json` with Node 22. Linux and Windows commands share the same
pytest configuration and synthetic fixtures. Platform-specific differences are
recorded when optional PostgreSQL, Docker, codecs or model artifacts are absent;
they are reported as skips/blockers rather than silently substituted.
