# Detailed full-consultation evaluation — 2026-10-29

## Dataset and fixed comparison

The selected source is [MedDistractAudio](https://huggingface.co/datasets/NYU-OLAB/MedDistractAudio), revision `bcef38c2bc8404d52a2c66a799be778e28216102`, derived from pinned [PriMock57](https://github.com/babylonhealth/primock57). Both are CC BY 4.0 public mock-consultation resources. This is a controlled background-consultation challenge rather than a collection of isolated clean utterances. Saved upstream ASR transcripts, generated notes and automated judgments are **not** imported as gold labels.

The frozen development subset contains eight complete foreground consultations, their clean recordings and one paired -10 dB donor-speech mixture each: **16 recordings, 158.03 audio minutes, 13,683 unique scored reference words and 1,004 words of clinician-written reference notes**. Clean duration is 79.015 minutes; paired conditions do not create sixteen independent patients. Individual recordings last 7.63–14.30 minutes. These cases cover gastrointestinal, dermatological, neurological, urinary and respiratory presentations, with histories, medications, explicit negative findings, assessments and plans. This does not establish a 20–30-minute natural-consultation accuracy result.

Selection was the first eight eligible foregrounds in the frozen pair table, before local inference. The three reserved acceptance encounters are excluded as both foreground and background donors. Some day1 excerpts were used in earlier development, so this is not an unseen or training-independent acceptance cohort. Human TextGrid references retain all words inside uncertainty tags; annotation tags themselves are removed under the existing scoring policy. The preliminary raw count of 14,600 included tag names; **13,683** is the scored count. Uncertain and inaudible reference regions still need independent listening/adjudication.

Each waveform is decoded losslessly and compared with its published PCM SHA-256. Parquet files, licenses and source metadata are bound to the pinned release. The [manifest](../evaluation/datasets/meddistract-detailed-v1/manifest.json), [lock](../evaluation/datasets/meddistract-detailed-v1/lock.json) and [selection protocol](../evaluation/datasets/meddistract-detailed-v1/protocol.json) were frozen before ASR.

## Models, ranking and ablations

The [active suite](../evaluation/detailed-suite-v2.json) includes tiny.en, Whisper small, MultiMed Whisper small English, distil-large-v3, Whisper large-v3, Parakeet TDT v2, Qwen3 ASR 0.6B and Omi. Omi's exact native-zero-token adapter fix is a separately labelled same-weight variant, giving nine runtime comparisons across eight distinct models. The original Omi behavior and any failures remain visible.

All candidates receive the same complete clean and distracted sources, initially through nonoverlapping 30-second windows. A failed chunk makes the whole case fail with all reference deletions; successful raw chunks remain available for diagnostics. No case, reference word or donor insertion is removed to improve a score. Incomplete, initialization-blocked and resource-timed-out candidates are unranked and visible, with no invented WER.

The primary ranking uses exact unrounded micro WER across the eight clean foregrounds, followed by paired distracted WER and observed latency. Distracted WER uses foreground-only references, so background words remain contamination errors. Scores for the two conditions are reported separately. Foreground-cluster bootstrap intervals are exploratory, not clinical acceptance bounds. The maximum remains **5%**, and neither a numeric pass nor a native timestamp can authorize clinical release.

After baselines finish, the two best complete candidates with distinct weights receive overlap-aware and speech-aware chunking experiments. A selected Whisper model additionally receives native long-form context decoding. Chunking uses audio energy, never reference text or human timestamps, and verifies full source coverage. Text stitching retains removed-overlap counts. Chunk bounds are never labelled model timestamps. Whisper native segment bounds are validated separately and do not establish word alignment or independently verified timing accuracy.

The first attempt stopped after a Windows sharing violation during atomic report replacement. Its published report, unpublished prefix and interruption receipt remain preserved. Suite v2 changes publication durability, normalizes source-code hash line endings and reuses only complete cases with matching model configuration, original input hash, exact reference and exact scores. The unfinished case is rerun in full. Reused case timings are explicitly not a fresh whole-corpus latency measurement.

## Run and inspect

Only already installed public/local model artifacts are used. No paid calls or gated terms are authorized. Models and local Qwen drafting cooperate through the existing local inference admission lock; application ASR can queue while a benchmark occupies it. Runs may take hours on this 16 GB CPU workstation. Each completed candidate and its diagnostic report is committed and pushed. A one-off finalizer waits for the owned campaign to exit, audits saved outputs and publishes a final ranking, chunking comparison and execution receipt. It never claims a complete comparison if models or required ablations are unfinished. Its temporary Windows system-awake request lasts only for the owned job and does not change persistent power settings. Runtime logs remain under ignored/transient paths; JSON evidence is versioned.

```powershell
.\.venv\Scripts\python.exe -m services.detailed_campaign status
```

The evolving [ranking](../evaluation/reports/detailed-ranking-v2-2026-10-29.json) shows completed and unranked work. The original interrupted ranking remains separate. Source hashes in suite v2 prevent silently changing execution code mid-campaign. The parent controls a model subprocess tree, records timeouts and preserves partial reports. Do not start a second campaign against the same result directory.

For a fresh data preparation, install `pyarrow==26.0.0` into `data/dataset-runtime` and run `python -m services.prepare_detailed` with **new** root/publication paths. Existing frozen manifests are never overwritten. Dataset audio and distribution shards stay under ignored `data/`; only selected source metadata and evidence are committed.

## Clinical and role diagnostics

`services.detailed_diagnostics` reports per-consultation edits, reference-role edit attribution, literal medication/dose/allergy/negation mention changes, token deletions and donor-only eight-token matches. These are lexical diagnostics: they do not establish predicted speaker accuracy, correct medication bindings, negation scope or independently adjudicated clinical omissions. Reference-role labels are not model-predicted roles. The finite medication lexicon is explicitly reported and is not comprehensive medical terminology coverage.

The separate detailed drafting screen compares deterministic output with pinned local Qwen 1.5B and 7B on complete upstream clinician-note units. It retains every line/semicolon clause and exact note-character evidence. Fixture eligibility flags are not clinician attestations. This screen measures exact preservation, bounded failures and model runtime, not clinical note accuracy, proper SOAP classification or clinician correction time. Full note units are not asserted to be adjudicated atomic clinical facts. Its failures remain included.

## Long-source proposal batches

The detailed source audit found 1,881 deterministic assertion-span proposals across the eight clean sources. The longest case produces 302, exceeding the single-note limit of 300. The application now requests up to 20 original source segments per local extraction call. Every batch remains bound to the complete source version/hash and records unprocessed segment IDs. Model output and relationship proposals remain separately saved and unreviewed; a model verdict cannot attest source completeness.

The UI retains each source batch, shows processing coverage separately from clinician review, and lets a clinician select relevant proposals before adding them to the editor. Prior selections survive subsequent batches. Adding proposals clears their review flags, duplicate source spans are avoided and the 300-fact note bound remains enforced. Semantic checks reset after a saved note version changes, while extraction batches remain valid for the unchanged source. Existing stale-source and revoked-authorization publication fences still apply. Tests prove that the 302-span case can be split without losing any exact source evidence; they do not establish that lexical spans are clinically complete atomic facts.

The completed [reference-note preservation screen](../evaluation/reports/detailed-drafting-summary-2026-10-29.json) independently checks saved statements against fixture units: deterministic 8/8 exact, Qwen 1.5B 3/8 exact with two failed cases, Qwen 7B 0/8 exact with eight failed cases under the configured 60-second bound. These are transport/preservation outcomes, not clinician correction-time or clinical note-accuracy measurements.

## Reviewers and clinician study

The user confirmed that independent reviewers are unavailable. Two [source-only reviewer packets](../evaluation/reviewer-packets/meddistract-detailed-v1) have no model output, upstream summary note, donor identity or condition metadata. Opaque audio aliases and the operator mapping are under `data/human-review/meddistract-detailed-v1`; distribute each reviewer packet separately. Blinding concerns ASR/model output, not an assertion that listeners cannot recognize background noise or repeated speech. These development labels cannot replace the separately reserved acceptance cohort.

The draft three-arm study compares manual notes, deterministic templates and local Qwen proposals. It includes a frozen proposed pair roster, counterbalanced draft orders and **zero observations**. A qualified owner must finalize training/washout, reviewer qualifications, independent correctness adjudication and any institutional requirements. Missing and failed arms remain counted. No automatic model runtime is substituted for observed clinician work.

The application's timed-review control now records a self-reported drafting approach, preserves it across corrected note versions and rejects idempotency retries that attempt to relabel it. This is operational attribution, not independently verified exposure. Wall time includes pauses; clinical errors/omissions require independent annotation. Source edits, stale approvals and AI-versus-approved note separation remain enforced.

## Identify and test physical hardware

The user does not know the microphone/interface model. In a new encounter, confirm synthetic recording authorization, select the physical channel count, then choose **Identify microphone and check channels**. The browser briefly opens the selected input, reads its label/settings/capabilities, stops every track and offers a local JSON download. No audio is stored or uploaded by this check. Permission cancellation and late grants release the tracks safely.

A reported channel count does not prove separate physical inputs, correct routing, cross-talk or clock accuracy. Connect a synchronized interface, record identifiable speech on one physical input at a time, then record known distinct calibration tones/pulses, interruptions and a full 20/30-minute session. Preserve the WAV and device-check receipt; inspect independent per-channel playback and run `services.channel_signal_audit` with the explicitly chosen frequencies/tolerance. Bind observed hardware, drivers, channel mapping and an independent time reference to the existing hardware-review packet. Generated tones and fake browser devices must never be entered as a physical hardware pass.

## Verification and current limits

The full backend regression, production build and targeted browser scenarios cover the added device, review-timing and source-batch behavior; exact results are recorded in the engineering validation receipt. Other model-dependent browser tests are not rerun concurrently with the resource-exclusive campaign. Ongoing measured results remain separate from completed engineering checks. The existing 5% gate, no-paid-call policy, clinician confirmation of roles and separation of proposals from approved notes remain unchanged. Independent annotation, clinician observations, physical routing/drift measurements and institutional approval are **not complete**. A final model winner cannot be announced while the comparable campaign is unfinished.
