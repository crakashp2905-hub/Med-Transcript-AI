# Completion review: engineering gaps and measured limits

This follow-up covers the user's ten requested workstreams and the remaining local engineering gaps. The attached checklist remains planning context; unrelated imaging, extra languages and production/EHR deployments were not silently added. Public local models only; no paid calls. Institution/clinical-owner identification remains skipped.

## Implemented

- Conservative extraction now separates explicit atomic source clauses, preserves exact offsets and decimals, and populates explicit medication/dose/allergen/laterality slots without inventing missing details. It remains a limited rule extractor, not general clinical language understanding.
- Verification checks omitted source terms, source words outside all evidence spans, swapped drug-to-dose assignments, changed negation scope, exact mass/volume unit equivalence, and structured-field/polarity/subject/time contradictions. A long explanation cannot waive definite contradictions. Explicit clinician-entered additions remain distinct. Previously approved versions remain immutable.
- The editor preserves all typed fields, exposes structured clinical details and resets review attestations when those fields change. Legacy facts receive schema defaults; audit-only fields are not resubmitted.
- Timed review is available in the interface. Server-observed wall time, word edits, added/removed facts and per-field edit counts are recorded without note text in telemetry. Wall time includes inactivity; no verified active clinician time or productivity improvement is claimed. Start retries reuse the client request ID; conflicting completion replays fail explicitly.
- Exact fact-level note comparison shows added/removed/changed fields and source-version changes. Both versions are encounter-scoped and immutable. Lists expose the latest 100 versions/sessions with an explicit limit.
- Optional local model extraction and an independent-model semantic reviewer now have typed interfaces, bounded schema output, exact evidence validation, per-call model digest checks, prompt/schema hashes, runtime/usage provenance and post-inference authorization/current-version checks. Their immutable proposals cannot become approvable notes, clear rule findings or overwrite saved notes. Failed/incomplete/invented-citation responses are rejected.

The extraction model is Qwen 2.5 1.5B; the independent verifier is Qwen 2.5 7B, with a separate prompt. New optional routes are `/fact-proposals`, `/semantic-checks` and `/clinical-proposals/{id}` under an encounter. Semantic batches cover at most 20 evidence-linked facts and explicitly identify unchecked facts. Use `scripts/start.ps1 -WithAsr -LocalDrafting -LocalClinicalModels -Port 8002`. Experimental public diarization remains a separate `-PublicDiarization` option. A local model opinion is not clinical truth.

## New evaluation evidence

The public Apache-licensed Qwen3-ASR 0.6B CPU INT8 conversion was provisioned from the official sherpa release, pinned by archive SHA-256 and evaluated on every unchanged 118-clip reference. It scored **311/2,264 = 13.7367% normalized WER**, zero failed clips. It ranks third in the separate [eight-model ranking extension](../evaluation/expanded-extension-leaderboard-v2.md), behind Omi 8.70% and Parakeet 13.25%. Every measured local candidate fails 5%. This is a post-hoc public candidate extension, not an independently preregistered acceptance result; the original seven-model suite and publications remain intact. No reference prompts or hotwords were supplied; chunk/word timestamps were not produced, so it was not promoted into application inference.

Reproduce provisioning with `python -m services.provision_qwen_asr`. Reproduce the report using `services.benchmark_text --runtime sherpa-qwen3`, the frozen expanded manifest, provisioned model directory, archive digest as `--revision`, and `data/diarization-runtime` as `--package-dir`. The report's revision is the converted archive digest, not an asserted upstream commit. Rebuild the ranking with `services.benchmark_ranking --manifest evaluation/datasets/primock57-expanded-v1/manifest.json --lock evaluation/datasets/primock57-expanded-v1/lock.json --ledger evaluation/expanded-extension-ledger-v2.json --out evaluation/expanded-extension-leaderboard-v2.json`. A failed WER gate intentionally gives the benchmark command a nonzero exit.

The six new synthetic rule challenges all matched their developer-authored expected labels (3 unsafe, 3 safe). The real independent verifier returned admissible outputs for 4/6, with 2 rejected failures. It incorrectly called the omission case supported; the deterministic omission check still required review. Both real extraction examples returned incomplete content and coverage findings. These small development tests establish neither clinical sensitivity nor accuracy. The initial model report predates the subsequent per-call digest/usage metadata guard; new application requests record those fields. See [model challenge results](../evaluation/reports/completion-clinical-models-2026-10-25.json) and the [versioned original adversarial rerun](../evaluation/reports/clinical-adversarial-v2-2026-10-25.json). The older v1 report is preserved.

## What cannot honestly be marked finished

| Release requirement | Current evidence |
|---|---|
| A local ASR meeting the strict 5% ceiling | None: best 8.70% on the shared clip corpus; Omi 13.05% on the full-consultation corpus |
| Reliable diarization | Public baseline weighted DER 50.91%; experimental, clinician role confirmation still required |
| Clinically calibrated extraction/semantic verification | Developer fixtures and real local model probes only; omissions and failures remain |
| Independent clinical gold and clinician correction-time study | Requires qualified human review; not performed or substituted with AI-generated truth |
| Real-patient pilot, institutional privacy/security approval | Not authorized or performed; current application remains synthetic-only |
| Hosted/gated comparisons | Disabled under the user's public-local/no-paid constraint |

Those are unmet validation/approval requirements, not checkboxes that code can truthfully close. No threshold was relaxed, no failed case was dropped, and no clinical or institutional sign-off was invented.
