# Manual-only versus assisted comparison protocol v1

The four MTA-16-02 correction cases form the paired task set. Both arms receive the same source reference, source text, and intentionally imperfect initial note state. The manual-only arm receives no proposal. The assisted arm receives a pre-scripted ideal proposal so product interaction can be compared without pretending a model produced it.

The assisted timing profile is a transparent demonstration constant: transcription 900 ms, fact extraction 500 ms, and drafting 300 ms, totaling 1,700 ms per task. These are simulated values, not measurements of the local model or ASR. Observed model runtime, clinician active time, and time saved remain null. No productivity or accuracy comparison is calculated from this protocol.

For a future real comparison, replace the ideal stimulus with a hash-identified local candidate, preserve failed and incomplete attempts, counterbalance task order, use independently reviewed source truth, and collect qualified human review time separately from machine runtime. Keep all tasks paired by ID and source state. The protocol itself has no human participants and grants no clinical acceptance.
