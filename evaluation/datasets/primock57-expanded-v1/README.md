# Expanded PriMock57 development comparison

118 fixed clips from 20 consultations across all five recording days, 830.097625 seconds total. The dataset ID retains the original 120-clip target; actual coverage is 118 and every result must include all 118.

Source: Babylon Health PriMock57, pinned revision `cd2ac707ad03cb4d2531f4ec6b90c659bf4357c5`. CC BY 4.0; see LICENSE.md and ATTRIBUTION.txt. These are public acted consultations, not actual patient recordings. Audio was normalized to mono 16 kHz PCM16 and cropped with 250 ms padding; upstream reference text was retained unchanged.

The first up to three eligible intervals per doctor/patient track were selected before inference: 4–20 seconds, at least five whitespace-delimited reference words and no annotation tags. `day5_consultation02_patient` has only one eligible interval; the pre-inference amendment in `../../expanded-protocol-v1.json` records this. No consultation was replaced based on difficulty or model output.

All 20 consultation IDs are disjoint from the original six-clip screening and 30-clip follow-up sets. Four consultation groups come from each recording day. Speaker independence and training-data independence are unknown; selected clean, separately recorded speaker tracks do not establish real microphone, noisy conversation or clinical acceptance accuracy.

`manifest.json` contains the frozen references, clip hashes, source hashes, intervals and protocol hash. `lock.json` records the exact manifest hash and the user-revised **≤5% normalized WER** maximum. Earlier corpora retain their historical 3% thresholds. Failures remain full-reference deletions and also fail the gate.

All seven local configurations use text-only benchmark adapters, so timestamps are outside this comparison. The older MultiMed pipeline-inclusive score counted timestamp validation failures; it must not be compared directly with this text-only result. No model is automatically promoted into the clinician application.

To regenerate public source material into ignored storage:

```powershell
.\.venv\Scripts\python.exe -m services.prepare_validation --protocol evaluation/expanded-protocol-v1.json --destination data/datasets/primock57-expanded-rebuild
```

Model artifacts and isolated optional runtime packages must already be locally provisioned and match `../../expanded-suite-v1.json`. The suite never downloads models, approves gated terms or calls hosted services:

```powershell
.\.venv\Scripts\python.exe -m services.benchmark_suite --lane a
.\.venv\Scripts\python.exe -m services.benchmark_suite --lane b
```

Run the lanes in separate terminals. Complete valid reports can be reused after interruption; incomplete/invalid reports require review. Per-clip progress and full model outputs are written under ignored `data/datasets/primock57-expanded-v1/results/`. These concurrent accuracy runs do not establish warmed throughput or latency.

`../../expanded-whisper-profiles.json` records the five original Windows source profiles in full. Their canonical configuration hashes match the pre-inference suite declaration; absolute paths identify this execution host. Scoring the committed reports is portable. Inference on a different host requires explicit local profile paths and a separately recorded configuration declaration, while retaining the pinned artifact hashes and decoding settings.

After all seven full local runs finish, publish the ledger, ranking, playable page and grouped report with `python -m services.publish_expanded`. To reproduce the committed scores without running models: `python -m services.benchmark_ranking --manifest evaluation/datasets/primock57-expanded-v1/manifest.json --lock evaluation/datasets/primock57-expanded-v1/lock.json --ledger evaluation/expanded-ledger.json --out evaluation/expanded-leaderboard.json`, then `python -m services.expanded_summary`. Runtime package versions are recorded in `../../expanded-runtime-versions.json`.
