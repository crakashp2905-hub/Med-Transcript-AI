# ASR evaluation and model admission

## Required WER limit

The user revised the strict maximum normalized WER from **3% to 5%** on 24 October 2026. Earlier frozen evaluations retain their original 3% gate; new evaluations default to 5%.
The runner now applies this gate by default, compares unrounded counts, exits
with status 2 on failure, rejects any processing failure and cannot accept a
looser threshold. `--max-normalized-wer` may specify a stricter fraction only.
An empty reference denominator cannot pass. The gate covers the aggregate
reference-transcribed evaluation dataset; subgroup and per-recording reports,
independent acceptance material and clinical safety adjudication remain required.
WER cannot be calculated for a new recording without a verified reference.

The selection policy is recorded in `evaluation/selection-policy.json`.
The older six-clip tiny.en report predates enforcement and fails both the historical 3% gate and current 5% gate
at 16.42%. It remains a development fixture. There is no production winner yet.

The benchmark runner is `python -m services.evaluation`. It accepts a local
manifest with `dataset_id`, `split_role`, `data_class` (`synthetic` or
`approved_public`), explicit `rights_reviewed: true`, and uniquely identified
samples. Each sample declares `sample_id`, `group_id`, `language: en`, a relative
`audio` path beneath the manifest directory, `audio_sha256`, and `reference` text.
Use already normalized mono 16 kHz PCM WAV evaluation audio; version and record
any separate preprocessing so engines receive the same material.

```powershell
python -m services.evaluation --manifest data/evaluation-manifest.json --profiles data/asr-profiles.json --profile-id YOUR_PROFILE --out data/comparison.json
```

Artifacts are checked before execution; API-equivalent transcript/timestamp
validation runs before scoring. The runner never downloads models or accepts
license gates. It reports raw and normalized word error rates. Normalization
preserves decimal values, unit words and negation. Failed samples are empty
hypotheses, so their reference words remain deletions in the denominator; counts
and safe failure codes are explicit. There is no accuracy score based only on
successful easy clips. Empty-reference hallucinations retain insertion errors
and have undefined WER when the corpus denominator is zero.

Hypotheses/reference text are excluded by default; use `--retain-hypotheses`
only for permitted private analysis under ignored data storage. Sample groups
must remain together across train/development/acceptance splits. Do not count
paired noise variants as independent clinical encounters. The runner does not
claim clinician adjudication, confidence intervals or release acceptance from
one generated fixture. Critical drug/dose/unit/negation errors and omissions
require reviewed annotations. Timing here includes model initialization per
sample and is not a warmed-throughput or p95 capacity benchmark.

The existing `evaluation/model-registry.json` lists all blueprint candidates.
The generic harness currently executes CTranslate2/faster-whisper-compatible
profiles. Other architectures/services require their admitted adapters, exact
artifacts, license/access decisions and authorized accounts; no scores are
fabricated for them. Hosted audio and hosted text are distinct disclosures, and
neither is enabled in this local MVP. Gated terms, remote GPU rental, paid provider
calls, and patient-audio disclosure are not authorized by a passing software test.

## Executed consultation probe

On 23 October 2026 the pinned `Systran/faster-whisper-tiny.en` revision
`0d3d19a32d3338f10357c0889762bd8d64bbdeba` ran against the generated 23.06-second
English consultation. It produced plausible text but estimated the last segment's
end at 26.44 seconds, outside the actual recording. The validator rejected that
result; the run reported one failed sample, 61 reference words and 61 deletions
(normalized WER 1.0 under the explicit failure policy). This is a safety-rejected
one-sample probe, not evidence about general clinical accuracy or an engine ranking.
The separate 7.26-second integration smoke did produce valid timestamps and pass.
The guard was kept intact rather than relaxed to make this probe pass.

Production engine selection therefore remains open. The large-v3 control,
medical challengers, representative independent English corpus, blinded clinician
review, critical-error adjudication and release thresholds still require the
blueprint's controlled evaluation work. The working clinician UI uses an audible,
explicit synthetic reference transcript to demonstrate review independent of a
model's errors; it does not present that reference as measured ASR output.

## Expanded local comparison

The predeclared `evaluation/expanded-protocol-v1.json` selects 120 utterances from 20 new consultations across five recording days, before inference. All seven locally runnable configurations use text-only adapters and unchanged decoding settings. This measures recognition separately from clinical timestamp/publication admission. In particular, MultiMed timestamp failures in the old pipeline-inclusive ranking are not comparable to this new text-only ranking. No reference edits, outcome-dependent exclusions or model tuning are permitted. Failures still contribute all reference words as deletions and fail the gate.

`services.benchmark_suite` runs two bounded local lanes in isolated processes, checks the predeclared source profiles/artifact hashes, saves per-clip progress logs and complete reports, and validates reports before reuse. Models are initialized once per dataset run; timings include that different lifecycle and concurrent CPU contention, so these are accuracy comparisons, not speed or capacity benchmarks. Hosted/gated/resource-blocked candidates remain explicit and unranked; no paid calls or access approvals are enabled.
