# Drafting adapters and diarization

Drafting defaults to the deterministic local provider. `POST /v1/encounters/{id}/draft-proposals` accepts the current transcript version and reviewed typed facts. Results are immutable proposals in a separate table, with provenance and source fact snapshots; they never become approvable notes automatically. Retrieve a proposal with the corresponding GET route. Model statements cite known reviewed fact IDs, obey a bounded JSON schema and undergo independent critical-field checks. Omissions and paraphrases remain review findings. Clinician approval/export continues through the existing note workflow.

For a provisioned OpenAI-compatible local text server, configure environment variables before starting the API:

```text
MED_TRANSCRIPT_DRAFTING_MODE=local
MED_TRANSCRIPT_LLM_ENABLED=1
MED_TRANSCRIPT_LLM_ENDPOINT=http://127.0.0.1:PORT/v1/chat/completions
MED_TRANSCRIPT_LLM_MODEL=YOUR_PROVISIONED_MODEL
```

Local endpoints must resolve entirely to loopback. No local LLM has been downloaded or clinically qualified by this change. The HTTP adapter is covered by a local fake-server integration test, not a real model quality result. Disabled adapters fail explicitly; failures never silently become a generated note.

Hosted configuration additionally requires mode `hosted`, an exact HTTPS public-host allowlist in `MED_TRANSCRIPT_LLM_ALLOWED_HOSTS`, an environment-only `MED_TRANSCRIPT_LLM_API_KEY`, enabled flag and `MED_TRANSCRIPT_LLM_BILLING_CAP_CONFIRMED=1`. That last flag confirms a separately configured provider-side spending cap; it does not implement a dollar meter. The encounter must be `hybrid_text`, have an active `hosted_text_processing` authorization scope, and each proposal request must explicitly accept hosted disclosure. Fully local encounters cannot send text to hosted drafting. The application remains synthetic-only. **No paid calls are authorized or made.** Account setup, provider terms, privacy approval and any future paid evaluation require the user.

Requests have bounded input/output, output token limits, a 30-second default timeout, no redirects and one attempt without retries. API keys and raw prompts/responses are not logged. Model, prompt hash, schema, parameters, measured wall time and safe token counts are retained; hosted cost remains unknown until verified pricing is supplied. Recheck authorization and transcript hash after generation; revoked/stale output is discarded. Revocation does not instantly abort an in-flight HTTP transport; the timeout bounds that work. DNS-rebinding hardening, provider contracts and production egress controls require deployment review.

`services.diarization.diarize` implements an optional sherpa-onnx offline adapter for approved local segmentation and embedding models, verifying supplied hashes and mono 16-kHz PCM input. It returns anonymous speaker clusters on the source timeline, unknown roles and overlap diagnostics. `confirm_roles` requires an explicit clinician confirmation and mapping of every cluster; source channel labels must never substitute for automatic prediction. Existing transcript editing supports clinician corrections to roles.

This adapter has not run against a licensed model/runtime on this workstation and is not integrated into the application worker. Its experimental manifest requires `enabled`, `license_approved` and verified model paths/hashes. Provisioning is blocked on licensing: [sherpa model documentation](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/models.html) lists Reverb segmentation with non-commercial terms and pyannote segmentation requiring upstream access. No terms were accepted. After the owner selects and approves a compatible model/runtime, validate the [Python API](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/python.html), measure diarization error/overlap/role corrections on independently annotated recordings, and integrate only after those checks pass. Current role confirmation tests are not measured diarization accuracy.
