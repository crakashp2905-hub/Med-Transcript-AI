# Formal evaluation method

The evidence graph is `audio → immutable transcript → source spans → typed
claims → note statements → approved export`. Every claim carries a typed
subject/predicate/object, polarity and exact evidence IDs. Missing fields stay
unknown; they are never inferred from a model score.

The machine policy reports a vector of critical contradictions, omissions,
false blocks and unresolved claims before any scalar cost. A critical
contradiction or unresolved claim forces abstention, and a critical contradiction
always blocks approval even if a caller supplies zero or negative-looking scalar
weights. This is a development safety policy, not a clinical accuracy estimate.
