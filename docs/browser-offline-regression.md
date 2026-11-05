# Offline browser regression

All application HTTP(S) requests in the browser fixture are denied outside loopback. This is application-request interception, not an operating-system firewall or proof that the browser itself has no background networking.

Use the cached dependencies and installed Chrome. No installation is part of these commands:

```powershell
.venv/Scripts/python.exe -m tests.offline_browser_server --allow-scripted-non-asr --port 8004
# In a second terminal:
$env:MED_TRANSCRIPT_TEST_URL='http://127.0.0.1:8004'
$env:npm_config_offline='true'
npx --offline --prefix apps/clinician-web playwright test --config apps/clinician-web/playwright.config.ts --grep-invert 'Google|google'
```

Run Playwright from `apps/clinician-web` if using its relative fixture paths. The server uses isolated UUID-named storage, the existing private local key, cached synthetic demo files and strictly hashed marker files. It executes real API, authorization, consent, queue, ingest, transcript-validation, review, approval and export paths. Its explicitly scripted adapter returns developer-written text regardless of audio; `inference_executed=false` and the source/model profile identifies a non-ASR test fixture. It is not a speech-recognition test, a clinician study or a real microphone validation. No production configuration can enable this fixture server.

The first native-model browser run at commit `ec428cf99b2c8cbbaad4285c5a231ff7107b45d0` retained 25 passes and one failure: server-backed sealing completed, but the ASR job returned `invalid_asr_output`. Audio was retained and no invalid transcript or approval was published. A scripted smoke pass must never replace that negative native result.

Early fixture bring-up failures also remain local JSON receipts: absent demo assets and marker manifests in a directory containing unrelated files were rejected. The fixture now uses a separate exact-manifest directory and verifies it before startup; production integrity validation was not bypassed.

For account-free simulated OIDC, run `python -m tests.google_browser_server --allow-simulated-provider --port 8005`, then run only `google-auth.spec.ts` against port 8005. Keep `MED_TRANSCRIPT_OFFLINE=1` and unset the strict local-key profile for this separate simulated-provider fixture. The browser intercepts the sign-in redirect before any Google request. Actual signature/issuer/audience/nonce/expiry checks are tested separately with locally signed tokens. This does not activate or certify live Google sign-in.

Test reports must distinguish native-model, scripted and simulated-OIDC modes, retain failed/aborted attempts, and keep independent clinical gold and clinical release false.
