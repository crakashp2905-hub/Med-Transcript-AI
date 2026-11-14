# Scripted correction task simulation v1

The offline encounter scenario pack includes four deterministic correction scripts: a medication dose swap, a source-supported allergy omitted from the note, a negation flip, and a speaker-role correction. Each script identifies the source reference, before state, target state, and task instruction. The replay harness checks whether the scripted result matches its supplied source and records it as an unapproved proposal.

The harness executes data-level correction bookkeeping. It does not observe a person, measure task time, establish that the fictional clinical facts are true, exercise the browser interface, or grant approval. `human_observations` remains zero and `clinical_acceptance` remains false by design. Browser interaction counts, latency, and errors belong to MTA-16-03; clinician UX and clinical validity require appropriately qualified human review.
