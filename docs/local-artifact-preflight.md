# Read-only local artifact preflight

Run `python scripts/offline_preflight --out data/NEW-PREFLIGHT.json` from the existing project environment, or `./scripts/offline_preflight.ps1 -Out data/NEW-PREFLIGHT.json` on Windows. Use a new output name each time; reports are exclusively created and earlier results are preserved.

This inspects cached Python wheels, installed package versions, npm dependencies, codec/tool availability, dependency/config hashes and every model file under the workspace model directory. Model hashing streams bounded blocks rather than reading weights into memory. No model is loaded, no account is activated and no dependency or weight is downloaded. Model symlinks/escapes or files that change during inventory are rejected.

The first recorded inventory contains 11 model directories, 93 files and 11,458,946,085 bytes. Exact hashes identify observed bytes, not model eligibility, license approval, inference validity or the 5% WER gate. Directory presence alone is separately labelled unverified. Missing runtime weights produce `model_unavailable`; changed bytes produce `model_integrity_failure`. Neither case admits output or triggers a hosted fallback. The saved audio and manual transcript path remain available.

For an existing Ollama cache, pass `--ollama-root LOCAL-CACHE` to the Python command or `-OllamaRoot LOCAL-CACHE` to the PowerShell wrapper. The wrapper also reads the configured `OLLAMA_MODELS` path. Only the project's pinned Qwen 1.5B and 7B manifests and referenced blobs are hashed; unrelated cached models remain outside scope. The separate first Qwen receipt verifies both manifests and seven unique blobs totaling 5,669,136,331 bytes. Its executed source snapshot is preserved with the report. These checks establish cached bytes, not drafting quality or clinical eligibility.

Coverage, Ruff, mypy and pip-audit are absent locally; the wheelhouse and local Docker/TLS packaging environment also remain unavailable. A hosted CI success does not manufacture these local caches. The no-model scripted demo remains usable, and clinical release remains blocked.
