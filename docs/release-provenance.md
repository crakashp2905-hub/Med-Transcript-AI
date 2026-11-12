# Release candidate provenance binding

`services.ci_provenance` emits a structured `MED_TRANSCRIPT_CI_PROVENANCE=` line
at the end of each successful CI job. The receipt binds the GitHub run ID,
attempt, job and checkout SHA to a canonical digest of the acceptance code
inventory and the detailed development dataset manifest. A checkout SHA
mismatch or dataset-lock mismatch fails the job.

Offline acceptance reports now record the starting commit, code-manifest digest,
dataset manifest digest and available GitHub run context. They fail source
integrity if either the tracked inventory or commit changes while acceptance is
running.

A release candidate binding references the acceptance report, code-manifest
file, dataset manifest/protocol/lock files and all five expected CI job receipts.
Each receipt must hash correctly and agree on one commit and run ID. The code
manifest must match the named Git commit tree; the acceptance report must match
the code and dataset digests; every acceptance check and CI job must pass. Run
the check with:

```powershell
$env:RELEASE_CANDIDATE_JSON = Read-Host "Path to the exported release candidate binding JSON"
python -m services.release_provenance $env:RELEASE_CANDIDATE_JSON --root .
```

This validates local byte integrity and linked metadata. It does not
authenticate GitHub or independently establish that an exported receipt truly
originated from the named hosted workflow. Hosted run artifacts still require
trusted acquisition and human review. The validator never authorizes clinical
use.
