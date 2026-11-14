# Offline diagnostics

Run the local diagnostics command with the repository's existing Python environment:

```powershell
.venv/Scripts/python.exe -m services.offline_diagnostics
```

It reports the current Git commit and tracked worktree state, hashes of source files included by offline acceptance, whether the latest acceptance snapshot is still fresh, configured local model directories that are present or missing, disk free space, directory read/write probes, blocked checks and failed/skipped tests from the latest hash-matched acceptance report, and the Python/Node toolchain versions.

The command makes no network requests, installs nothing, and does not load model weights. Directory permission probes create and immediately remove temporary files. Model directory presence does not verify model weights or eligibility. A missing or stale acceptance report is reported as unavailable or invalidated, never as a pass. The optional `--out PATH` writes a new JSON report and refuses to overwrite an existing file.
