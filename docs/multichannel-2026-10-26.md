# Multichannel scribe implementation — 2026-10-26

The application accepts one synchronized recording with 1–8 physical channels. Two was a PriMock57 benchmark source constraint, not a speaker limit. Multiple clinicians, a patient, interpreter and caregiver can occupy distinct channels, but channel identity is not proof of speaker identity.

## Capture and uploads

Select an input device and physical channel count in Microphone dictation. Mono retains the compressed recording path. Two or more channels use an AudioWorklet and interleaved PCM16 WAV at the browser AudioContext sample rate (requested 16 kHz). Echo cancellation, noise suppression and automatic gain control are disabled for multichannel requests. The device must report the requested channel count; otherwise capture fails visibly and stops its tracks. One compatible synchronized audio interface is required. Separate USB microphones, files with different start times, and independently clocked devices are not automatically synchronized or combined.

Browser capture remains bounded by 30 minutes and 64 MiB, whichever occurs first. At 16 kHz PCM16 this is approximately 17.5 minutes for two channels, 11.7 minutes for three and 4.4 minutes for eight. Size limits or interruptions retain a partial WAV for explicit review, download or retry. Recording lives in browser memory; closing or reloading the tab can lose unsaved audio. Input-device labels may require browser microphone permission. Real physical multichannel hardware has not been validated on this workstation; automated tests use generated independent channel signals.

Upload a synchronized multichannel WAV for longer workflows. The upload and normalized output limits are 250,000,000 bytes, up to 60 minutes, and eight channels; high channel counts can hit the byte limit first. PCM16 RIFF WAV is the canonical input. Supported compressed containers must contain a single audio stream, may contain several channels, and must have a recognized fixed channel layout. Multiple separate audio streams and video remain rejected. Resampling preserves channel order; it no longer downmixes. Decoder failures publish no usable normalized asset.

## Inference and evidence

The worker verifies source hashes and isolates each channel as exact mono PCM, then transcribes all channels using the selected registered development profile. Every channel has the same recording origin; output segments are merged by start time with overlapping intervals retained. Each segment carries its zero-based channel index and an anonymous channel identifier. Untranscribed intervals and provenance remain available separately for every channel, including silent channels. A failed channel fails the job without publishing a partial transcript. Existing leases, authorization checks, idempotency and source-version fences still apply. Temporary isolated worker files are cleaned on normal completion or exceptions.

Channel identifiers are anonymous inputs, not recognized people. Review channel leakage, cross-talk and speaker changes. Roles start unknown; a clinician can confirm clinician, patient, caregiver, interpreter, other or unknown and correct individual turns. Confirmation creates a new immutable source version. Multiple people may share the same role; identities are not inferred. Physical channels bypass the optional fixed-window speaker-clustering baseline.

Source turns, note evidence buttons and verification navigation select the cited channel before seeking. Playback also offers an explicit channel selector. Isolated playback uses an authenticated, encounter-scoped endpoint, checks the source hash, and serves a temporary mono WAV with range support; normal response cleanup removes it. Playing the original multichannel mix depends on browser codec/channel support; isolated playback avoids that dependency. Source corrections preserve channel references, and historical notes continue to use their original source asset and transcript version.

## Quality and scope

The application still uses the registered tiny English development ASR profile. No evaluated timestamped candidate qualifies for the unchanged 5% normalized WER gate. Multichannel transport does not establish clinical accuracy, speaker reliability, production readiness or independent clinical acceptance. No paid models, external audio calls, automatic role assignments or automatic note approvals were introduced. Separate asynchronous uploads and word-by-word live streaming are outside this implementation.

## Validation

Backend coverage includes 2-, 3- and 8-channel sample isolation, shared overlapping timestamps, per-channel gaps, scoped channel playback, channel-preserving source edits, failed-channel atomicity, nine-channel rejection, and three-channel 48-to-16 kHz resampling. Browser coverage includes generated three-channel PCM capture with distinct signal amplitudes and a retained retry file, plus rejection of a device reporting too few channels. Existing dictation and clinician review workflows remain regression checks.

The full Python regression suite passed 195 tests with one local PostgreSQL skip. Final channel/transcription checks passed 26 tests, and channel/media checks passed nine. The TypeScript/Vite production build passed. Browser checks also exercise worklet rejection when device settings claim three channels but actual delivered audio has fewer. The worklet is served from the same origin under the existing content-security policy.

A real-worker smoke run is recorded in `evaluation/reports/multichannel-real-worker-2026-10-26.json`, reproducible with `python -m services.multichannel_smoke --output <new-report.json>` against the isolated localhost:8003 test workspace. Three distinct, hash-verified public PriMock57 development utterances are padded to a common 8.311-second origin; this assembled stress input is not an actual multi-party consultation. All three channels completed with valid timestamps, unknown/unconfirmed roles and no automatic note or approval, in 57.24 seconds including ingestion and polling. The tiny development profile made 14 normalized errors in 71 reference words (19.72% aggregate WER). This fails the unchanged 5% gate; the transport smoke provides no clinical acceptance evidence. The report retains per-channel references, hypotheses, isolated PCM hashes, gaps and provenance.

Final browser regression: all 12 Playwright workflows passed in one run (1.9 minutes), including the existing clinician approval/export and compressed-upload flows.
