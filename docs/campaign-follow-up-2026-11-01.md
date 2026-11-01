# Campaign follow-up — 2026-11-01

The nine fixed-window runtime variants have completed the frozen 16-recording development comparison. None meets the unchanged 5% normalized WER gate. The highest-ranked baseline is Omi native-empty (16.41% clean, 17.22% distracted), followed by faster-whisper-large-v3 (20.69%, 21.68%). These results do not establish clinical approval or timestamp eligibility.

Three finalist chunking experiments completed: Omi overlap, Omi speech-aware and Whisper large overlap. Each performed worse on clean WER than its corresponding fixed-window baseline. Whisper large speech-aware stopped with 14 completed recordings and context mode with 7. Partial recordings and original reports remain preserved; no whole-corpus WER is assigned to those runs. Rerunning them requires a fresh protocol/output location and a bounded execution plan; the immutable completion receipt is unchanged.

The study dashboard now prefers the published final ranking, includes source file SHA-256 values, shows baseline completion separately from finalist experiment completion, and lists incomplete experiments explicitly. It still cannot promote a model, clear a note approval gate or claim independent clinical validation.

Validation: five targeted backend tests passed, including final-ranking preference, absent-evidence handling and suppression of partial experiment scores; TypeScript and production build passed. Human reviewers, physical hardware validation, and institutional/EHR acceptance remain external dependencies.
