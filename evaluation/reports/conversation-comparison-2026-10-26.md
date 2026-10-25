# Full-conversation development comparison — 2026-10-26

Three frozen public mock consultations; 5,204 reference words, 31m39.6s total audio. Individual recordings are about 8–13 minutes. This is development evidence, not independent clinical acceptance. Separate-channel conditions receive a different input modality from the mixed baseline.

| Condition | Edits / words | Normalized WER | Failed case/role runs |
| --- | ---: | ---: | ---: |
| Mixed fixed 30s baseline | 679/5204 | 13.05% | 0 |
| overlap | 768/5204 | 14.76% | 0 |
| speech_aware | 746/5204 | 14.34% | 0 |
| two_channel | 2097/5204 | 40.30% | 2 |
| overlap, post-hoc filler-tolerant stitch | 761/5204 | 14.62% | 0 |
| speech_aware, post-hoc filler-tolerant stitch | 734/5204 | 14.10% | 0 |
| Two-channel native-empty reconstruction | 775/5204 | 14.89% | 0 |

The best aggregate remains the original 13.05% baseline. The 5% gate remains unchanged and unmet. No text-only Omi condition supplies validated utterance/word timestamps. No application promotion occurred. Every condition preserves original input coverage; input coverage does not prove transcript completeness.

## Per consultation, mixed audio

| Consultation | Fixed 30s | Overlap | Energy-selected | Filler-tolerant overlap | Filler-tolerant energy |
| --- | ---: | ---: | ---: | ---: | ---: |
| day1_consultation11 | 309/2328 (13.27%) | 361/2328 (15.51%) | 374/2328 (16.07%) | 361/2328 (15.51%) | 362/2328 (15.55%) |
| day1_consultation12 | 171/1178 (14.52%) | 197/1178 (16.72%) | 181/1178 (15.37%) | 195/1178 (16.55%) | 181/1178 (15.37%) |
| day1_consultation13 | 199/1698 (11.72%) | 210/1698 (12.37%) | 191/1698 (11.25%) | 205/1698 (12.07%) | 191/1698 (11.25%) |

## Per role, separate source channels

Roles here come from upstream source-track labels; these are not automatic application role assignments.

| Consultation | Reference role | Original edits / words | Original failed | Empty-output reconstruction edits / words |
| --- | --- | ---: | --- | ---: |
| day1_consultation11 | doctor | 929/929 | True | 187/929 (20.13%) |
| day1_consultation11 | patient | 180/1399 | False | 180/1399 (12.87%) |
| day1_consultation12 | doctor | 87/636 | False | 87/636 (13.68%) |
| day1_consultation12 | patient | 86/542 | False | 86/542 (15.87%) |
| day1_consultation13 | doctor | 122/1005 | False | 122/1005 (12.14%) |
| day1_consultation13 | patient | 693/693 | True | 113/693 (16.31%) |

## Literal clinical-term comparison

These are fixed-lexicon mention differences, not adjudicated medication/dose/negation or clinical-concept accuracy. Full counts for every original condition are retained in the JSON reports.

| Condition / consultation | Role | Missing mentions | Extra mentions |
| --- | --- | --- | --- |
| fixed30 / day1_consultation11 | mixed | diarrhoea: 2 | diarrhea: 2 |
| fixed30 / day1_consultation12 | mixed | diarrhoea: 5 | diarrhea: 5 |
| fixed30 / day1_consultation13 | mixed | None in lexicon | None in lexicon |
| empty-output reconstruction / day1_consultation11 | doctor | diarrhoea: 1, pain: 1 | diarrhea: 1 |
| empty-output reconstruction / day1_consultation11 | patient | diarrhoea: 1 | diarrhea: 1 |
| empty-output reconstruction / day1_consultation12 | doctor | diarrhoea: 1 | diarrhea: 1 |
| empty-output reconstruction / day1_consultation12 | patient | diarrhoea: 4 | diarrhea: 4 |
| empty-output reconstruction / day1_consultation13 | doctor | None in lexicon | None in lexicon |
| empty-output reconstruction / day1_consultation13 | patient | None in lexicon | None in lexicon |

## Failure and provenance notes

The initial driver stopped while printing a nonexistent summary key after saving its first completed case. That interrupted report is retained. The resumed report binds its digest, checks the reference/model/configuration, and reuses the verified completed case.

The original separate-channel run failed two case/role runs because six native empty string results were rejected by the Python wrapper. A separate probe reproduced all six exact wrapper errors. The opt-in adapter accepts only that exact empty-output condition; genuine native failures still raise. The post-hoc reconstruction reuses unchanged successful chunks and admits those native empty outputs as empty hypotheses. It does not overwrite the original failures, claim a fresh full rerun, or remove reference words. Empty text can still omit speech. The legacy adapter default and historical clip rankings remain unchanged.

The filler-tolerant stitch is also a post-hoc development ablation. It only tolerates unmatched fixed-list filler words, retains unmatched doses/negations, and records every fuzzy decision for audio review. It can still remove real repeated speech. It is not used in application inference.

Error diagnostics preserve original source-turn indices and per-role word counts. Insertions are assigned to the preceding reference role as a diagnostic heuristic. Source-turn time bounds locate reference turns and are never presented as ASR word alignment.

Reproduce with `services.conversation_experiment`, `services.omi_failure_probe`, `services.omi_empty_reconstruction`, `services.overlap_reassembly`, and `services.conversation_errors`. Supply distinct output paths: the commands preserve earlier evidence. See the source files for their CLI arguments.

Raw evidence: [resumed ablation](conversation-ablation-resumed-2026-10-26.json), [interrupted attempt](conversation-ablation-2026-10-26.json), [failure probe](omi-failure-probe-2026-10-26.json), [empty-output reconstruction](two-channel-empty-reconstruction-2026-10-26.json), [filler-tolerant reassembly](overlap-reassembly-2026-10-26.json), [all-condition error diagnostics](conversation-all-errors-2026-10-26.json).
