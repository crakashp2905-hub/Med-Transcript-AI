# Read-only local artifact preflight

Run `python scripts/offline_preflight --out data/NEW-PREFLIGHT.json` from the existing project environment, or `./scripts/offline_preflight.ps1 -Out data/NEW-PREFLIGHT.json` on Windows. Use a new output name each time; reports are exclusively created and earlier results are preserved.

This inspects cached Python wheels, installed package versions, npm dependencies, codec/tool availability, dependency/config hashes and every existing local model file. Model hashing streams bounded blocks rather than reading weights into memory. No model is loaded, no account is activated and no dependency or weight is downloaded. Model symlinks/escapes or files that change during inventory are rejected.

The first recorded inventory contains 11 model directories, 93 files and 11,458,946,085 bytes. Exact hashes identify observed bytes, not model eligibility, license approval, inference validity or the 5% WER gate. Directory presence alone is separately labelled unverified. Missing runtime weights produce `model_unavailable`; changed bytes produce `model_integrity_failure`. Neither case admits output or triggers a hosted fallback. The saved audio and manual transcript path remain available.

Coverage, Ruff, mypy and pip-audit are absent locally; the wheelhouse and local Docker/TLS packaging environment also remain unavailable. A hosted CI success does not manufacture these local caches. The no-model scripted demo remains usable, and clinical release remains blocked.
