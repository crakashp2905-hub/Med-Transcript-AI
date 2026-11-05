# Historical drafting-screen diagnosis

This eight-case development screen measures exact preservation of supplied source-note fixture units. It does not measure clinical note accuracy or clinician correction time.

| Arm | Exact preservation | Failed executions | Other completed but non-exact cases |
| --- | --- | --- | --- |
| Deterministic | 8/8 | 0 | 0 |
| Qwen 1.5B | 3/8 | 2 | 3 |
| Qwen 7B | 0/8 | 8 | 0 |

The saved provider failures have the category `bounded_provider_failure`; a more specific runtime cause is not established by that receipt. Do not relabel all eight failed 7B runs as incorrect clinical statements or infer a factuality percentage. The three additional 1.5B cases completed but did not exactly preserve all expected section/text/fact-ID tuples. The deterministic arm copies supplied reviewed fixture facts, so its 8/8 is a preservation control, not a clinical advantage estimate.

The original runs and digests remain in [the saved screen](../evaluation/reports/detailed-drafting-2026-10-29.json). [The scope-separated baseline report](../evaluation/reports/scope-separated-baselines-v1.json) retains all three arms. `services.detailed_finalize.draft_summary` independently reconstructs each output's tuples and rejects missing/duplicate cases or scalar preservation claims that disagree with actual statements.

The next prospective comparison must use frozen identical inputs, prompts, digests and budgets. Smaller prompts, schema constraints and decomposed subtasks are distinct ablations, not repaired scores for this historical run. Deterministic reviewed-fact drafting stays available throughout; models remain unreviewed proposals and cannot clear approval gates.
