# Local dependencies: provisioned and tested

The user requested work on dependencies, then explicitly kept **public local models only, no paid calls**, and skipped institution/clinical-owner sign-off. No clinical or institutional signature has been simulated. No gated or non-commercial model terms were accepted.

## Local drafting

Ollama was already installed with Qwen 2.5 1.5B and 7B Q4_K_M models. Both report Apache 2.0 licenses; model digests and runtime version are recorded in the reports. The actual local endpoint was tested with four synthetic cases, covering medications/doses, negation, family attribution, allergy, laterality, timing and instruction-like source text.

| Configuration | Schema/citation failures | Exact section/text/citation cases | Review findings |
|---|---:|---:|---:|
| 1.5B, JSON object baseline | 2/4 | 1/4 | 5 |
| 7B, JSON object baseline | 1/4 | 0/4 | 18 |
| 1.5B, constrained JSON schema | 0/4 | 2/4 | 13 |
| 7B, constrained JSON schema | 0/4 | 0/4 | 22 |

The optional local launch profile selects **Qwen 2.5 1.5B with schema constraints**, because it had no schema failures, better exact preservation and lower measured latency than the larger constrained candidate. This is a four-case development screen, not proof of clinical drafting quality. Changes to facts or sections are flagged; proposals never replace or approve notes. Initial failures remain committed. The recorded latency includes workstation load and cold-model loading and is not a controlled service-level benchmark. Local provider charges are zero; hardware/electricity cost remains unmeasured.

Reports: `evaluation/reports/local-drafting-2026-10-25.json` and `local-drafting-structured-2026-10-25.json`. Reproduce with `python -m services.local_drafting_evaluation` and add `--structured --output PATH` for the constrained variant. The exact screened model digest must be installed before the launch profile enables it. Remote/cloud Ollama model tags are not selected.

## Public diarization baseline

Provisioned sherpa-onnx **2.0.0 plus matching sherpa-onnx-core 2.0.0**, Silero VAD and the English WeSpeaker VoxCeleb ResNet34 LM embedding model. Artifacts are SHA-256 checked before inference. Silero is MIT; **WeSpeaker code is Apache 2.0, but VoxCeleb weights follow CC BY 4.0** under the upstream model-license documentation. Model files, licenses and attribution stay under ignored `data/models/public-diarization-v1`; code and reports are committed. These artifacts avoid gated segmentation weights.

```powershell
.\.venv\Scripts\python.exe -m pip install --target data/diarization-runtime --upgrade --no-deps sherpa-onnx==2.0.0 sherpa-onnx-core==2.0.0
.\.venv\Scripts\python.exe -m services.provision_public_diarization
$env:PYTHONPATH='D:\Med-Transcript\data\diarization-runtime'
.\.venv\Scripts\python.exe -m services.diarization_evaluation
```

The full 31m39.6s corpus has been processed. At cosine threshold .65, predicted cluster counts are 19, 44 and 30 for two-reference-speaker consultations; zero-collar, overlap-inclusive diarization error is **47.84%, 56.55%, 50.78%** against upstream TextGrid labels. Lowering the threshold to .35 merged both people into one cluster and worsened the results. All configurations and failures remain visible; development parameter comparisons must not become an acceptance claim. Upstream labels have not been independently adjudicated. This fixed-window VAD/embedding method cannot separate overlapping voices and can straddle speaker changes. It is an experimental baseline, not a reliable replacement for manual attribution.

Aggregate speaker-duration-weighted DER: **50.91% at .65, 54.49% at .50, 55.07% at .35**. The optional provisioned profile retains .65; lowering fragmentation did not improve the aggregate result. These thresholds were compared on development cases and do not define an independent acceptance result.

Worker integration is now implemented and opt-in. It runs after ASR under the existing lease/authorization lifecycle and stores anonymous speaker intervals in the immutable transcript. A text segment is assigned a cluster only if exactly one cluster covers at least 80% of it; crossings and weak coverage stay unknown. Clinicians can play cluster examples and confirm all roles in the source UI. The corresponding scoped, ETag-protected `/transcripts/{id}/speaker-roles` endpoint creates a new source version; existing notes become stale. It never infers “doctor” from reference metadata. Speaker embeddings are not stored in transcripts or reports.

## Use the provisioned features

```powershell
.\scripts\start.ps1 -WithAsr -LocalDrafting -Port 8002
```

Add `-PublicDiarization` only when deliberately testing the experimental clustering baseline. Default launches retain deterministic drafting and omit automatic clustering. Stop an existing workspace on the selected port before changing its inference configuration. The launcher checks the screened local drafting digest and provisioned diarization artifacts; it makes no paid calls. On the note tab, review facts and select **Generate proposal from reviewed facts**. The proposal remains separate from the saved note. Role confirmation appears when an inferred transcript contains clusters.

An isolated synthetic workspace was started at `http://127.0.0.1:8002` with both options enabled for development testing. A real application smoke test completed synthetic audio upload, ingest, ASR, public-model clustering and local Qwen proposal generation. No note was approved/exported; speaker roles stayed unknown. See `evaluation/reports/dependency-application-smoke-2026-10-25.json`. The frontend compiled and API integration tests passed. Visual browser verification was unavailable because browser setup failed with a restricted-module error; no visual inspection is claimed.

## ASR and skipped human dependencies

The 5% normalized WER gate is unchanged. The earlier best Omi result is 8.70% on the 118-clip screen; none of those local candidates is eligible for clinical promotion. `services.full_consultation_asr` provides a complete-source development test of that leader on the new long cases, using fixed non-overlapping 30-second input windows and retaining all intervals. It strips annotation markup while retaining enclosed uncertain words, records failures as empty case hypotheses and exposes the unchanged lexical gate. Input-window boundaries are not word timestamps, and references still require clinical adjudication.

The completed [full-length Omi result](../evaluation/reports/full-consultation-omi-2026-10-25.json) has **679 edits / 5,204 reference words = 13.0477% normalized WER**, with zero processing failures over all 64 windows and all 1,899.6 seconds. Consultation results are 309/2,328 (13.27%), 171/1,178 (14.52%) and 199/1,698 (11.72%). The strict 5% gate fails. Offline verification checked the frozen manifest hash, contiguous coverage from zero to each recording's exact end, retained reference words and recomputed case scores. Total measured ASR execution was about 595 seconds on this workstation, with concurrent development activity; this is not a controlled latency SLA. These cases have different full-length references and input chunking from the earlier screen, so the percentages are not interchangeable.

The user skipped institution/clinical-owner identification. Clinical gold adjudication, a real correction-time study, institutional privacy/security approval and real-patient pilot authorization remain unperformed; an AI coding agent cannot supply qualified human review or sign-off. No reviewer identity, clinical accuracy, time saving or legal approval has been invented. Paid/gated models remain disabled. Hardware provisioning does not guarantee the 5% target.

Sources: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [Qwen 1.5B model card](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct), [WeSpeaker pretrained model license](https://github.com/wenet-e2e/wespeaker/blob/master/docs/pretrained.md), [Silero license](https://github.com/snakers4/silero-vad/blob/master/LICENSE), [sherpa speaker identification](https://k2-fsa.github.io/sherpa/onnx/speaker-identification/index.html).

Validation: **130 local tests passed, one PostgreSQL test skipped locally**. The dependency implementation passed all five jobs in [GitHub run 40213593436](https://github.com/crakashp2905-hub/Med-Transcript-AI/actions/runs/40213593436), including the isolated PostgreSQL integration and container build. Frontend production build passed.
