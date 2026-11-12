# Clinical error review triage

The provisional taxonomy in [clinical-impact-triage-v1.json](../evaluation/clinical-impact-triage-v1.json)
orders saved ASR lexical edits for human review. It places explicit identity or
speaker attribution flags, medication names, dose or strength values, allergy
terms, and negation cues in the first review tier. Frequency, numbers or units,
and chronology cues follow. Other lexical edits remain visible in the third
tier.

The implementation at `services/clinical_impact_triage.py` uses a small fixed
set of text patterns. Multiple categories can apply to one edit, so category
counts overlap and must not be summed. It only counts identity or speaker
attribution when a human annotation explicitly sets that flag; a reference role
is not a predicted role. A dose or strength cue requires a complete numeric and
unit span or an explicit independent `dose_context` annotation; a bare number
is only counted under number or unit review.

This is a queueing heuristic, not a measured harm ranking, calibrated severity
score, or clinical gold label. A qualified clinical reviewer must validate and
revise the order before using it to prioritize real-patient review. The
independently weighted concept endpoint remains separate and requires human
impact weights; no default weights are assigned.
