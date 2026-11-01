# Bounded recovery of stopped Whisper experiments

Recovery protocol: `evaluation/detailed-recovery-v3.json`. Original v2 reports and the completion receipt remain unchanged. This supplements them; it does not replace the baseline ranking.

The runner executes speech-aware and context mode serially under the shared local inference lock. Each has an eight-hour limit, and waiting for admission has a one-hour limit. Windows timeout cleanup terminates only the owned child process tree. A temporary system-awake request is released on exit and does not change persistent power settings.

Every original resume report is SHA-256 pinned. Before completed recordings are reused, the benchmark checks model configuration, source waveform hashes, reference text, full-source coverage and exact score consistency. Any unfinished recording is rerun in full; partial chunks are not admitted as a completed case. Native failures retain the original whole-recording deletion policy. Source hashes and dataset hashes remain enforced under the new protocol. Source files are frozen for this recovery execution.

The recovery receipt is `evaluation/reports/detailed-recovery-v3.json`, and outputs use the separate `evaluation/runs/meddistract-recovery-v3` directory. Completed results are committed and pushed per experiment. Attempts cannot overwrite existing recovery reports. The dashboard displays original and recovered attempts side by side, including incomplete cases. Original case timings remain in recovered results; they are not a fresh whole-corpus latency measurement.

The 5% normalized WER gate is unchanged. No model is automatically promoted, no paid calls are authorized, and no independent clinical approval is implied. Completing computation does not substitute for unavailable clinical reviewers or hardware observations.

Validation before launch: 12 targeted tests passed, including both non-fixed recovery modes, unfinished-case rerun, original output preservation, source/model/score tamper rejection, failure-inclusive scoring and dashboard handling of partial results. Production frontend build passed.
