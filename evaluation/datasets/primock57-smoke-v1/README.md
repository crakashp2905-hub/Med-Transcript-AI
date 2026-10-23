# Frozen PriMock57 screening corpus v1

This directory is the versioned source of truth for the current screening
leaderboard: **six audio clips, 134 reference words, 45.21 seconds, one consultation**.
It includes the actual mono 16 kHz PCM recordings, manual reference transcripts
in `manifest.json`, exact checksums, upstream revision, attribution and CC BY 4.0
license. The dataset is simulated medical dialogue, not actual patient care.

Source: [Babylon Health PriMock57](https://github.com/babylonhealth/primock57),
Alex Papadopoulos Korfiatis, Francesco Moramarco, Radmila Sarac and Aleksandar
Savkov (2022). See `LICENSE.md` and `ATTRIBUTION.txt`.

Changes: normalized to mono 16 kHz PCM and cropped the first three eligible
4–20 second utterances per doctor/patient track from day 1 consultation 1,
with 250 ms padding. Selection preceded model comparisons. Uncertain and
unintelligible annotation tags were excluded from this initial screening set.

`lock.json` fixes the exact manifest hash, scoring profile and failure policy.
Do not edit these references or replace audio to improve a model score. Corrections
require a new corpus version and all candidate runs must be repeated for that
version. The ranking tool rejects incomplete coverage and different manifests.

The upstream annotations are benchmark references, not infallible clinical truth.
This tiny development set cannot establish general accuracy or clinical safety.
Independent full consultations, noise, overlap, accents, medications, doses, units
and negation cases are required for acceptance. Related clips belong together;
the six clips are not six independent consultations.

```powershell
.\.venv\Scripts\python.exe -m services.evaluation --manifest evaluation/datasets/primock57-smoke-v1/manifest.json --profiles data/YOUR_PROFILES.json --profile-id YOUR_PROFILE --out data/YOUR_RESULTS.json --retain-hypotheses
```

Model artifacts are provisioned separately. Failed 3% gates intentionally exit 2.
