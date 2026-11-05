# Candidate contribution: uncertainty-aware evidence and relation checking

This is a **hypothesis and candidate contribution**, not a claim of independent novelty or clinical effectiveness. Existing conservative rules remain the baseline. No reserved acceptance material may be used to design, select or tune this method.

Let the evidence graph contain audio assets A, immutable transcript versions T, segments S, exact character spans E, typed claim tuples C, note statements N and approved exports X. Edges retain encounter/version identity and hashes: A→T→S→E→C→N→X. A span is valid only when its quoted text exactly equals the selected source slice and its source identity matches the current immutable version.

Represent a claim as c=(subject, predicate, object, polarity, certainty, temporality, medication, value, unit, route, frequency, duration, laterality, evidence). Missing fields are unknown, not inferred. Quantities use exact decimal arithmetic over the explicitly supported conversion table; preserve the source surface form. Distinguish stopped/historical medication from a current prescription and clinician speculation from an established diagnosis.

For material field k, define disagreement d_k(c,e)=1 when an explicit claim contradicts its evidence, 0 when a validated rule establishes equivalence, and ⊥ when the rule cannot establish support. A critical disagreement is a hard block regardless of a model verdict. Any ⊥ requires review; there is no fabricated numerical confidence.

Let R be the set of clinically relevant source-span candidates and U the union of explicitly linked spans in the note. Report span coverage |R∩U|/|R| separately from clinically important omissions. Coverage measures retention of source text, not semantic completeness. Conversational fillers may be separately categorized but cannot be silently removed from frozen ASR denominators.

For exploratory comparisons, report the vector (critical misses, benign false blocks, unresolved claims, source retention, runtime, peak memory) before any weighted aggregate. If a scalar cost is explored, freeze weights and abstention penalties before evaluation; never let an average override a critical contradiction. A local model opinion can add a warning but cannot clear deterministic or human-review gates.

Compare lexical rules, relational rules, a local verifier alone and the proposed combined policy on identical developer-authored synthetic cases. Freeze prompts, labels, cases, budgets, model digests and endpoints before the run. Use paired intervals over cases/consultations; do not treat tokens or clean/distracted variants as independent subjects. Preserve timeouts and malformed/incomplete outputs as explicit failures or abstentions.

Required ablations remove one component at a time: relation attachment, negation scope, temporality, source coverage and model opinion. A candidate remains inconclusive when outputs are incomplete, paired cases are missing, the budget expires, provenance fails or uncertainty cannot resolve the prespecified effect. Slower or worse results remain published. Independent clinical gold and clinical release remain false throughout developer-only experiments.
