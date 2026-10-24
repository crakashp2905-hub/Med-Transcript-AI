# Frozen follow-up corpus: consultations 02–06

This is a separate development validation corpus for the two lowest-error
configurations from the initial six-clip screen. It contains **30 audio clips
from five additional mock consultations**, approximately 203.68 seconds of mono
16 kHz PCM16, with upstream manual references. Clips from the original selection
consultation are excluded.

The source revision, selection rules, model configurations, normalization,
failure policy and strict ≤3% WER gate were declared in
[`validation-protocol-v1.json`](../../validation-protocol-v1.json) before inference.
For each consultation and role, select the first three 4–20 second utterances
with at least five reference words and no uncertain/unintelligible tags, then
add 250 ms padding. References are unchanged. `manifest.json` and `lock.json`
bind exact reference/audio bytes and provenance. Corrections require a new version.

Source: [PriMock57](https://github.com/babylonhealth/primock57), Babylon Health;
Alex Papadopoulos Korfiatis, Francesco Moramarco, Radmila Sarac and Aleksandar
Savkov (2022), CC BY 4.0. See `LICENSE.md` and `ATTRIBUTION.txt`. Audio is acted
medical dialogue, not actual patient care. Changes are normalization and cropping.

This is **not clinical acceptance**. Selected clean utterances do not represent
full consultations, microphone conditions, overlapping speech or noise. Clinicians
may repeat across consultations, and model-training overlap is unknown. Upstream
references have not been independently clinically adjudicated. The two models'
text-only adapters do not supply validated clinical source timestamps. Drug,
dose, unit, allergy and negation review remains pending.

Do not mix these scores with the six-clip screening ranking. Both models must
receive the same complete manifest; all failures remain in the denominator.
