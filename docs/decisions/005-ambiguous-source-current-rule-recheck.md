# ADR 005: Ambiguous source claims and historical safety rechecks

Status: implemented for the local synthetic review workflow.

Source-linked statements must pass claim and structured-field checks even when the quote contains an uncertainty marker. A clarification field records context; it does not establish a changed dose, medication, negation, or other claim. An explicit clinician correction creates a new unapproved note version: the original source-linked quote is retained as an excluded fact, and the corrected statement is a separate clinician-entered fact without audio evidence. Approval remains a human action on the exact saved version.

Warnings include a validator identifier, affected fields, and a source reference with an exact quote hash. The review screen resolves the quoted source from the saved fact. A critical warning cannot be cleared by a model verdict or by changing only the clarification text.

Rules version 4 also binds source-level omissions to the exact uncovered word or critical term, including its segment and character offsets. The review screen displays the excerpt from the saved transcript and offers direct source playback. A clinician-entered addition has no audio citation and is labeled as such.

Saved verification reports and approvals are immutable. When a saved report predates the current rules, the workspace presents an additional read-only recheck against that note's exact original transcript. A new export request also runs the current rules, including requests for a previously generated export. If it finds a blocking issue, the request returns `current_safety_review_required`. Previously downloaded exports remain historical audit artifacts; their bytes are not silently changed or deleted. Operators should revoke or quarantine copies distributed before this rule change according to their local incident process.

The before and after reports in `evaluation/reports/ambiguity-guard-before-v1.json` and `evaluation/reports/ambiguity-guard-after-v1.json` use scripted synthetic transcripts and programmatic review flags. They establish a software safety regression, not clinical accuracy, clinician validation, or model eligibility. The 5% normalized WER gate and clinical release block remain unchanged.
