# Paired audio enhancement results

`evaluation/reports/audio-enhancement-paired-v3.json` is a fresh paired run of
the frozen six-utterance PriMock57 smoke set with the local Omi model. The
source audio, model artifacts, manifest, baseline run, candidate files and
transform source hashes are recorded in the report. Earlier v1 and v2 reports
were preserved.

The five arms were unmodified audio, whole-clip RMS normalization, bounded
short-time adaptive gain, an 80 Hz high-pass filter, and a percentile spectral
gate. Every arm completed all six samples without inference failures and scored
9 normalized edits over 134 reference words (6.72%). The transformations
produced no paired sample improvement or degradation on this smoke cohort. All
arms fail the unchanged 5% WER gate.

Adaptive gain uses 100 ms RMS windows, a 50 ms hop, a -24 dBFS target, a 12 dB
boost/cut bound, a -50 dBFS silence floor, smoothed gain changes, and a 0.98
peak ceiling. Synthetic tests check level tracking, silence preservation,
clipping bounds, frame count and source immutability. The transform remains an
offline experiment and is not enabled in application inference.

This small convenience-selected mock cohort is development-only. It is not a
speech enhancement quality claim, clinical validation, or model admission.
