# ASR training and inference feasibility

## Decision

Building an in-house inference system around already trained, rights-reviewed weights is feasible on the documented 16 GB CPU workstation and is the appropriate scope for this project. Training a new speech foundation model from scratch is not feasible from the repository's audio or compute budget. No CPU-only 5% WER promise is made.

## Available data

The frozen detailed evaluation set contains 16 clean/noisy recordings from eight consultation groups and about 1.32 aggregate recorded hours. The paired conditions share the same consultation content, so they are not 1.32 hours of independent linguistic coverage. The references are upstream mock transcripts, not independently adjudicated labels. This is a small development/evaluation set; it is not a foundation-model training corpus, and its evaluation groups must not be repurposed as training data.

## Scale and compute comparison

| Reference | Published data scale | Published training compute | Comparison to this repository |
|---|---:|---:|---:|
| wav2vec 2.0 LARGE pretraining on LibriVox | 53,200 hours of unlabeled audio | 128 V100 GPUs for 5.2 days, about 666 V100 GPU-days; model has 317 million parameters | About 40,300 times the repository's 1.32 aggregate audio hours |
| Whisper weakly supervised training | 680,000 hours of multilingual and multitask audio/transcript supervision | The paper reports the data scale; it is not used here to infer an unreported compute budget | About 515,000 times the repository's 1.32 aggregate audio hours |

These are published research reference points, not a direct cost forecast for a proposed in-house architecture. They show why a from-scratch foundation-model plan needs a separately licensed corpus measured in many thousands of hours and a multi-GPU training program. The published wav2vec 2.0 run alone is roughly 666 V100 GPU-days before data preparation, experiments, failed runs, fine-tuning, and evaluation. There is no defensible conversion from that GPU workload to this workstation's CPU wall time without implementing and benchmarking the selected architecture; no such local estimate or run is claimed.

## Feasible project path

The current project instead evaluates and integrates existing local model weights. The frozen suite covers the eight consultation groups in paired clean/noisy conditions, reports failures in the denominator, measures per-condition latency and full-process memory, and preserves the unchanged WER gate. Those runs demonstrate an engineering and benchmark path only. Their measured WERs remain above 5%, so none qualifies for inference-mode promotion. A future fine-tuning or adapter experiment would require its own rights-cleared training data, group-level split, independent untouched acceptance set, hardware budget, and preregistered evaluation; it would be a separate decision from both current inference and foundation-model training.

## Sources

- Baevski et al., [wav2vec 2.0: A Framework for Self-Supervised Learning of Speech Representations](https://proceedings.neurips.cc/paper/2020/hash/92d1e1eb1cd6f9fba3227870bb6d7f07-Abstract.html), including the 53.2k-hour LibriVox setup, 317M-parameter LARGE model, and 128 V100 / 5.2-day pretraining run.
- Radford et al., [Robust Speech Recognition via Large-Scale Weak Supervision](https://proceedings.mlr.press/v202/radford23a.html), reporting 680,000 hours of multilingual and multitask supervision for Whisper.
