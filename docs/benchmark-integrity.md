# Frozen benchmark integrity

Baseline snapshot: `evaluation/reports/engineering-baseline.json`. It records the pre-change commit, installed package versions and model-directory inventory, existing test/build outcomes and SHA-256 values for 198 report/manifest/protocol files. Model-directory presence is not proof of loadability.

`services.benchmark_integrity` replays committed full-consultation hypotheses without loading models. It checks case identity, exact reference text, audio identity, score arithmetic, failure-inclusive empty hypotheses and complete source coverage. A complete report must contain every predeclared case exactly once. Unknown, duplicate, missing and tampered cases fail. Original report/manifest bytes are never rewritten.

Keep separate: the selected 118-clip Omi result (~8.70% WER); three mock consultation result (~13.05%); and the frozen eight-foreground MedDistractAudio paired screen (Omi native-empty 16.41% clean / 17.22% distracted). These are not mutually independent acceptance cohorts or one universal score. Detailed baseline/recovery negatives remain in their original directories; recovery reuses validated complete cases and explicitly retains mixed original timings.

The primary WER retains uncertain reference words, decimals, negation and units. Wrapper-native empty output is a separately named runtime variant, not decoder failure erasure. Failed recordings retain full-reference deletions under their predeclared protocol. Chunk/segment timestamps are not word alignment, clinician role correctness or independently verified clinical accuracy.

Five-percent model admission remains failed and no model is automatically promoted. Developer source-note preservation and synthetic rule tests are mechanistic evidence, not clinical note-accuracy or time-saving estimates. All new exploratory parameters need separately versioned protocols; reserved acceptance data are not optimized on.
