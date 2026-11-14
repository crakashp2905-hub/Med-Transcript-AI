# Offline browser regression

All application HTTP(S) requests in the browser fixture are denied outside loopback. This is application-request interception, not an operating-system firewall or proof that the browser itself has no background networking.

Use the cached dependencies and installed Chrome. No installation is part of these commands:

```powershell
.venv/Scripts/python.exe -m tests.offline_browser_server --allow-scripted-non-asr --port 8004
# In a second terminal:
$env:MED_TRANSCRIPT_TEST_URL='http://127.0.0.1:8004'
$env:npm_config_offline='true'
Set-Location apps/clinician-web
npx --offline playwright test --grep-invert 'Google|google'
```

For a clean run without touching the existing `data/local-config.json` or prior browser artifacts, create a unique workspace and seed its synthetic example first. In terminal 1, from the repository root:

```powershell
$repo=(Resolve-Path .).Path
$runId=[guid]::NewGuid().ToString('N')
$runRoot=Join-Path (Join-Path $repo 'data') "browser-acceptance-$runId"
New-Item -ItemType Directory -Path $runRoot | Out-Null
Set-Location $runRoot
$env:PYTHONPATH=$repo
$env:MED_TRANSCRIPT_PROFILE='no_external_dependency'
$env:MED_TRANSCRIPT_OFFLINE='1'
& "$repo\.venv\Scripts\python.exe" -m services.launch --demo --no-worker --port 8004
# After it prints that the workspace is serving, press Ctrl+C. The isolated
# data/local-config.json and demo sample are now seeded in $runRoot.
& "$repo\.venv\Scripts\python.exe" -m tests.offline_browser_server --allow-scripted-non-asr --port 8004
```

In terminal 2, from the repository root, set `$runRoot` to the same unique directory and run:

```powershell
$repo=(Resolve-Path .).Path
$runRoot=Join-Path (Join-Path $repo 'data') 'browser-acceptance-<same-run-id>'
$access=Get-Content (Join-Path $runRoot 'data/local-config.json') -Raw | ConvertFrom-Json
$out=Join-Path $runRoot 'artifacts'
$env:MED_TRANSCRIPT_TEST_KEY=$access.access_key
$env:MED_TRANSCRIPT_TEST_OUTPUT_DIR=$out
$env:MTA_BROWSER_ARTIFACT_DIR=Join-Path $out 'usability'
$env:MTA_TIMING_OUTPUT=Join-Path $out 'timing-report.json'
$env:MTA_METRICS_OUTPUT=Join-Path $out 'metrics-report.json'
$env:MED_TRANSCRIPT_TEST_URL='http://127.0.0.1:8004'
$env:npm_config_offline='true'
Set-Location (Join-Path $repo 'apps/clinician-web')
npx --offline playwright test --grep-invert 'Google|google' --output (Join-Path $runRoot 'playwright')
```

Keep `$access` and all key-bearing objects out of logs. The specs use the injected key when present and otherwise retain the repository-local fallback for existing workflows. The versioned output root redirects generated microphone fixtures, downloads, screenshots, usability observations, timing metrics and Playwright traces so previous evidence is not overwritten.

The server uses isolated UUID-named storage and strictly hashed marker files. It executes real API, authorization, consent, queue, ingest, transcript-validation, review, approval and export paths. Its explicitly scripted adapter returns a fixed local PriMock57 reference string regardless of audio; `inference_executed=false` and the source/model profile identify a non-ASR test fixture. The browser dictation timing fixture uses the corresponding public mock utterance with trailing silence. This is not a speech-recognition test, a clinician study, or real microphone validation. No production configuration can enable this fixture server.

The first native-model browser run at commit `ec428cf99b2c8cbbaad4285c5a231ff7107b45d0` retained 25 passes and one failure: server-backed sealing completed, but the ASR job returned `invalid_asr_output`. Audio was retained and no invalid transcript or approval was published. A scripted smoke pass must never replace that negative native result.

Early fixture bring-up failures also remain local JSON receipts: absent demo assets and marker manifests in a directory containing unrelated files were rejected. The fixture now uses a separate exact-manifest directory and verifies it before startup; production integrity validation was not bypassed.

For account-free simulated OIDC, run `python -m tests.google_browser_server --allow-simulated-provider --port 8005`, then run only `google-auth.spec.ts` against port 8005. Keep `MED_TRANSCRIPT_OFFLINE=1` and unset the strict local-key profile for this separate simulated-provider fixture. The browser intercepts the sign-in redirect before any Google request. Actual signature/issuer/audience/nonce/expiry checks are tested separately with locally signed tokens. This does not activate or certify live Google sign-in.

Test reports must distinguish native-model, scripted and simulated-OIDC modes, retain failed/aborted attempts, and keep independent clinical gold and clinical release false.
