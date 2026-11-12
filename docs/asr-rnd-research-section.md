# In house ASR research summary

## Hypothesis

A bounded local English ASR pipeline with source-linked review, careful segmentation, and optional medical terminology biasing may improve recognition of consultation speech while preserving clinically important wording. This is a development hypothesis, not a clinical performance claim.

## Method and baseline

The current baseline uses pinned local Faster Whisper profiles on mono 16 kHz PCM. The worker validates media, records model and source provenance, preserves native segment timestamps, and publishes a review-required immutable transcript. Evaluation uses locked public mock consultation groups and failure-inclusive normalized WER. The predeclared admission threshold remains WER <= 5%.

Experiments compare selected model profiles, segmentation modes, consensus decoding, audio conditions, and a small paired hotword pilot. Reports retain source manifests, model artifact digests, failed runs, and negative results where available. The full equal-compute ablation matrix has not been completed.

## Results and negative findings

No evaluated profile passes the frozen WER gate; the best expanded short-clip result is 8.70%. The small hotword pilot improved exact-term recall on four selected positive clips but increased false insertion on one of four negative clips and worsened aggregate WER from 28.76% to 30.07%. This is evidence of a bias tradeoff on a small development subset, not a gain or safe terminology feature.

The current evidence does not establish calibrated confidence, clinically safe speaker attribution, clinical critical-error rates, or end-to-end clinician acceptance. No learned correction, reranking, or model adaptation gain is claimed.

## Novelty and ablation limits

This work is an engineering evaluation of source-bound local ASR and review controls. It does not claim novel acoustic reranking or a new recognition architecture. A complete related-work comparison and full matched-compute ablations remain future work; no novelty claim should be made until those are completed and independently reviewed.

## Ethics and intended use

The available evaluation material is public mock consultation audio, not independent real-patient validation. There is no qualified clinical acceptance set or approved safety tolerance for medication, negation, omission, or patient-role errors. ASR output remains a candidate requiring clinician review; no evaluated model is qualified for clinical use or promotion. Future work requires appropriate data rights, privacy controls, qualified reviewers, adjudication, and explicit institutional approval before real-patient evaluation.

## Reproducibility pointers

- Frozen model selection rule: `evaluation/selection-policy.json`.
- Paired uncertainty and conditions: `evaluation/reports/paired-asr-bootstrap-v1.json`.
- Terminology bias pilot: `evaluation/reports/asr-lexicon-bias-pilot-v1-final.json`.
- Model cards and negative experiment inventory: `evaluation/reports/model-cards-v1.json` and `evaluation/reports/negative-experiments-index-v1.json`.
- Current objective decisions: `evaluation/reports/asr-objective-release-v1.json`.
