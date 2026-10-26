# Development delivery — 2026-10-27

Public local inference only; no paid calls or gated terms. This is a synthetic/public-mock development application. Engineering improvements do not authorize clinical deployment or establish the unchanged 5% WER requirement.

## Recording and recovery

Microphone audio is committed as ordered IndexedDB chunks scoped to tenant, clinician and encounter. Reload recovery is explicit, labelled incomplete, and cannot automatically upload or resume recording. The last uncommitted audio can be lost. Quota or slow-storage failures stop capture and retain the committed prefix. Discard and successful upload remove the local draft; deletion failures are surfaced. Browser storage remains unencrypted synthetic development storage; eviction, profile deletion, private browsing and device loss are not recoverable by this mechanism.

PCM capture uses short batches and an 8 MiB pending-write guard instead of a complete in-memory recording array. Whole-file hashing now streams SHA-256 through pinned `@noble/hashes` 2.4.0; upload chunks are at most 4 MiB. Blob backing and disk quota remain browser-managed. The capture/upload/normalized-output bound is 512,000,000 bytes, with a 30-minute capture and 60-minute ingest duration bound. Thirty minutes of eight-channel 16 kHz PCM16 uses approximately 461 MB; available browser quota and compatible hardware are still required. Mono intentionally permits downmixing; two or more channels require reported and actual matching channel counts.

The server accepts sequential, hash-checked upload chunks with durable offsets. Identical lost-response retries do not duplicate bytes; incorrect offsets, bytes, media types, authorization and final hashes fail. Uncommitted file tails are truncated to the committed offset. A rename completed immediately before a database crash can be recovered after validating the full file. Sessions still expire after 15 minutes; expiry can require a new upload session. Database migrations preserve earlier resumable offsets.

Capture checks active recording/local-processing permission periodically. Revocation or inability to verify permission stops capture without automatic upload. Stopping does not silently recreate a revoked grant. Explicit retries require the recording attestation, and recovered drafts require fresh confirmation. Generation guards isolate late permission responses and late media events from newer captures. Sign-out/navigation are guarded while recording or transfer is active.

## Local previews and worker recovery

Opt-in live previews process approximately ten-second PCM windows using the registered local development profile. Only one preview is pending from a capture at a time; busy intervals may be skipped for preview while the complete recording continues saving. Results show estimated timeline intervals and remain provisional. They never create transcript versions, notes or approvals. The full saved recording is transcribed separately after stopping. This is windowed preview, not word-by-word streaming, and recognition remains unqualified.

Preview windows are limited to 15 seconds. The synthetic preview cache expires after 900 seconds by default, configurable through `MED_TRANSCRIPT_PREVIEW_CACHE_SECONDS` (60–86400). Cleanup preserves legal holds and assets referenced by saved transcript versions, and retains non-text attempt history. This cache setting is not an institution-approved patient retention policy.

The worker retains one pinned loaded Whisper model per process, still checks artifact integrity, and records model-load/cache-hit/inference timing. Verified completed channels are checkpointed against job, original/working input, isolated PCM, model profile and output hashes. Failed channels do not publish partial source versions. Bounded explicit retries reuse only validated completed work. Failed and abandoned attempts remain recorded. Job progress and retry controls expose completed channels without making partial output approvable.

Local application ASR and optional local LLM requests share a nonblocking process admission lock. Busy worker jobs remain queued; optional LLM proposals fail visibly without changing saved notes. Deterministic extraction/drafting remains available. The lock path can be configured with `MED_TRANSCRIPT_INFERENCE_LOCK`; it is not a distributed scheduler, a memory quota or a guard for arbitrary external benchmark processes. Operate heavyweight benchmark tools serially on this 16 GB workstation.

## Clinical relationships

The deterministic baseline now proposes explicit route, frequency and duration fields when uniquely present. Typed relationship proposals retain exact segment/character quotes, explicit subject, entities, quantities, routes, timing, actions, condition and assertion. They are unreviewed lexical bindings, not clinical understanding. Unknown terms, pronouns and ambiguous scope remain limitations. Structured checks reject borrowing a different drug's dose or reaction elsewhere in the same evidence quote.

Blocking relationship checks supplement existing rules; model verdicts cannot clear them. The retrospective 52-case development comparison reduced unsafe misses from 13 to 0, with four false alarms remaining. Original reports remain unchanged, and the legacy-rule replay is explicitly versioned. These developer fixtures are not independent clinical gold or a sensitivity/specificity estimate.

The new frozen 16-case challenge had zero rule misses/false alarms. The separately run Qwen verifier admitted 15/16 verdicts and had one timeout, one omission miss and one safe-case false alarm. The combined human-review recommendation flagged all eight unsafe cases and one safe case. A preceding contended verifier run and its timeouts remain preserved with an interruption receipt. Neither run establishes clinical calibration.

## Expanded conversation evidence

Five additional complete pinned PriMock57 public mock consultations add 7,443 reference words. The previous best local development candidate, Omi, was tested with the unchanged 30-second fixed-window protocol. The strict failure-inclusive run scored 34.50% WER, including one whole-case failure caused by a final short-window failure. A separate unchanged-input probe reproduced exactly the known wrapper rejection of a native empty transcript. A separately labelled post-hoc reconstruction scored 15.48% with all reference words retained and no remaining processing failure. It is not a fresh run, independent acceptance or latency evidence. Both fail the 5% gate, and Omi still lacks model timestamps. No candidate was promoted.

Per-consultation, reference-role and literal clinical-term edit diagnostics are retained for both conditions. They use reference-turn attribution and do not establish predicted speaker accuracy, word alignment or adjudicated clinical concept accuracy. The original eight-candidate clip ranking remains tied to its own frozen dataset; it must not be compared as if all candidates ran on the new full recordings.

## Independent review and security dependencies

The reserved day5 consultations 05–07 were downloaded and checked against pinned upstream audio/annotation hashes solely for human-source preparation. Blank independent reviewer packets, a qualification registry, license, frozen source manifest/lock and source-audit receipt are under `evaluation/annotation-source/acceptance-v1`. These are outside the development dataset namespace. Development preparation and the full-ASR CLI reject reserved groups. No ASR/LLM ran on this cohort. Reference listening/correction, reviewer credential checks, independent annotation, third-reviewer adjudication, speaker/site/device/training independence and institutional approval remain unperformed human dependencies.

Optional encrypted backups use pinned `cryptography` 50.0.2 Cobblestone-128 authenticated streaming envelopes. Restore authenticates the entire envelope before extraction/publication, checks extraction budgets and paths, verifies existing file receipts and applies deletion tombstones. Tamper, truncation, wrong-key, overwrite and round-trip checks are covered. Temporary plaintext staging requires a protected/encrypted volume in deployment; file mode bits do not establish Windows ACL protection. Key custody, rotation, storage/database encryption, external audit, institutional SSO/MFA, approved retention and patient-pilot approval remain external deployment requirements.

Install optional operations support with `python -m pip install -e ".[security]"`. Generate a test key using `python -m services.encrypted_backup keygen --key-file data/local-backup.key`; never commit or print it. Use the CLI help for backup/restore paths and size budgets. Production keys require independently managed custody; locally generated test keys do not satisfy that requirement.

Controlled tone diagnostics in `services.channel_signal_audit` measure channel swaps, silence and cross-talk against supplied engineering tolerances. Generated test signals verify the software; physical interfaces, channel routing and independent timing still require observed hardware tests. The tool never marks physical hardware or clinical diarization validated.

## Validation

The backend regression passed 225 tests plus one local PostgreSQL skip before the final progress/admission additions; the final regression and browser checks are recorded in the completion receipt. Eighteen browser workflows passed before the final streaming-hash/consent-safe upload change. Focused rechecks and real-worker timing/duration results will be recorded separately. Hosted CI validates the API, optional ASR/security dependencies, PostgreSQL, frontend and container build. None of these functional checks establishes clinical accuracy.

References for the adopted library APIs: [incremental hashing](https://github.com/paulmillr/noble-hashes#implementations) and [authenticated streaming encryption](https://cryptography.io/en/50.0.2/cobblestone/).
