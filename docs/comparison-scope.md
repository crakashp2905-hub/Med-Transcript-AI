# Scope-safe model comparisons

The comparison preparation layer requires one dataset/task/evaluation scope per
view. Complete candidates may be ranked by normalized WER; failed, blocked and
missing candidates remain visible with no rank. Cross-dataset rows are rejected
instead of producing a misleading aggregate leaderboard. This is an evaluation
presentation safeguard, not a clinical performance claim.
