# Offline scripted encounter scenarios v1

This scenario pack exercises five scripted workflow conditions: short source
review, deterministic background noise, synthetic speaker overlap, a typed
medication-history correction, and two-channel speaker navigation.

Three of the audio fixtures are deterministic derivatives of locally included
PriMock57 public mock utterance clips; the multi-speaker fixture routes those
utterances to stereo channels by upstream reference role. The synthetic overlap
and noise transformations are documented in `manifest.json`. Source speech is
public mock speech, not newly recorded synthetic speech. The medication-heavy
case is developer-authored text only and has no associated audio or ASR result.

Attribution: PriMock57, Alex Papadopoulos Korfiatis, Francesco Moramarco,
Radmila Sarac and Aleksandar Savkov (2022), Babylon Health, CC BY 4.0. The
upstream dataset attribution and revision are recorded in the manifest. Changes
to the source clips are identified per scenario. See
`evaluation/datasets/primock57-expanded-v1/LICENSE.md`.

Regenerate with:

```powershell
python -m services.product_scenarios
```

These scenarios support scripted product-workflow testing only. They do not
establish ASR accuracy, clinician usability, clinical validity, independent
clinical acceptance or real-patient readiness. Reference roles are not system
predictions. No model inference is performed during generation.
