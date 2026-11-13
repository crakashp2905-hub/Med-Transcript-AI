# BECCSV research protocol v1

**Protocol state:** preregistered engineering hypothesis; not clinically validated.
**Scope:** English-language, clinician-supervised documentation assistance.
**Data policy:** local committed synthetic/public-mock data only. No real patient
data, paid calls, or external asset fetches are part of this protocol.

## 1. Falsifiable hypothesis (MTA-11-01)

The proposed method is **Bidirectional Evidence-Constrained Clinical State
Verification (BECCSV)**. Its testable claim is that, on a future independent,
source-audited consultation cohort, a typed source-to-note graph with checks in
both directions will reduce critical unsafe-claim misses by at least 20% relative
to deterministic checks alone, while increasing the consultation-level false
alarm rate by no more than 5 percentage points. The comparison is paired by
consultation. The primary confidence interval must exclude no improvement, and
the upper confidence bound for the false-alarm increase must remain within the
predeclared margin.

This is a hypothesis and a design threshold, not an observed result, clinical
tolerance, or release gate. The threshold must be reviewed by qualified,
independent clinical reviewers before an acceptance cohort is collected. If the
result misses either bound, or the cohort cannot be independently adjudicated,
the hypothesis is unsupported. No novelty claim is made against literature that
has not been systematically reviewed.

## 2. Method specification (MTA-11-02)

For one consultation, represent source facts as `S`, atomic note claims as `N`,
and typed evidence or consistency relations as `E`. A source fact stores its
value and clinical state: concept, polarity, subject/experiencer, temporality,
certainty, medication/dose/unit/route/frequency when applicable, speaker/role,
and an immutable source reference. A note claim stores the corresponding state,
section, source-fact identifiers, and cited evidence. Unknown or unreviewed
values remain unknown; absence of a mention does not create a negative fact.

An edge `s -> n` in `E` means that source fact `s` supports note claim `n` under
the typed comparison rules. Edge types distinguish exact evidence linkage,
state-preserving entailment, medication-to-dose binding, temporal relation,
subject attribution, and contradiction. An edge is not inferred from lexical
similarity alone. The verifier evaluates:

1. **Source coverage:** every required, non-excluded source fact is represented
   in the note or remains explicitly unresolved.
2. **Forward support:** every note claim has one or more valid supporting source
   facts or is marked clinician-entered with its distinct origin.
3. **State and relation consistency:** polarity, subject, certainty, time, and
   medication relationships are preserved; contradictions and unsupported
   bindings are findings.
4. **Abstention:** ambiguous evidence, conflicting speaker attribution,
   unavailable models, malformed output, or incomplete graph coverage cannot
   yield a clean verification result.

The model may propose a typed judgment. Deterministic graph and rule checks
remain the approval gate; a model verdict cannot clear a deterministic finding
or authorize a note.

## 3. Difference from simpler checks (MTA-11-03)

Ordinary rule checks test a fixed list of local conditions and often start from
the note, so they may miss omitted source facts. LLM self-critique asks a model
to review its own output and does not guarantee that every source fact and every
note claim was examined. BECCSV requires a typed, source-linked graph and checks
both the source-to-note direction (omissions) and note-to-source direction
(unsupported claims), plus typed relation/state consistency. This design does
not establish superiority; that is what the paired experiment tests.

## 4. Formal objects, loss, and algorithm (MTA-11-04 through MTA-11-06)

Let `S_r` be required source facts after explicit exclusion review, `N` be note
claims, and `E subset S_r x N x T` be typed support edges, where `T` is the finite
edge-type set above. Let `u(s)=1` when source fact `s` has no valid representation
or explicit unresolved state, `v(n)=1` when note claim `n` has no valid support,
and `c(e)=1` when a relation/state constraint is contradicted. The working
severity-weighted mismatch score is

`L = sum_s w(severity(s))*u(s) + sum_n w(severity(n))*v(n) + sum_e w(severity(e))*c(e)`.

For development-only summaries, weights are fixed, non-probabilistic ordinal
penalties: critical=8, high=4, moderate=2, informational=1. They are not risk
probabilities, clinical utilities, or calibrated values. The weights and
severity mapping must be reviewed and frozen before the independent cohort;
results must also report unweighted error counts so weighting cannot hide errors.

```text
VERIFY(S, N, candidate_edges):
  validate unique IDs, exact evidence spans, graph bounds, and typed edge schema
  if any required source state or speaker attribution is ambiguous:
      return findings + abstain
  E := retain only edges whose cited spans and deterministic state checks pass
  for each s in S_r:
      report omission unless s maps to a note claim or explicit unresolved item
  for each n in N:
      report unsupported claim unless n has a valid source or clinician origin
  for each linked (s, n):
      compare polarity, subject, certainty, temporality, and clinical relations
      report mismatch; never repair either side automatically
  return findings, coverage counts, L, and review-required status
```

With `|S|` facts, `|N|` claims and `|E|` proposed links, ID validation,
coverage, and relation checks are `O(|S| + |N| + |E|)` expected time using hash
maps, plus the cost of bounded text-span validation. Memory is
`O(|S| + |N| + |E|)`. Invariants: IDs are unique; each source edge resolves to
an exact immutable source span; excluded facts are not silently treated as
covered; every claim has a declared origin; model judgments never mutate source
facts or approval state; missing evidence produces abstention/findings; and
approval requires independent clinician action.

## 5. Abstention policy (MTA-11-07)

Abstain from a clean result when source text is ambiguous, speakers conflict or
are unconfirmed, a medication relationship is uncertain, temporal state is
missing, evidence is stale, a provider is unavailable, output is malformed, or
graph validation fails. Preserve the source and all findings. Do not guess a
speaker, resolve a pronoun, infer a dose, convert missing mention to negation, or
use an LLM verdict to remove a warning. The note remains a proposal until the
existing clinician approval workflow completes.

## 6. Deterministic-first implementation boundary (MTA-11-08)

The graph-only layer is the first implementation under test. Existing primitives
are `services/evidence_graph.py`,
`services/review/relationships.py`, and deterministic clinical rules. They
validate immutable source spans, graph structure and clinical relations without
requiring an LLM. Optional local model judgments remain a separate advisory
layer. The rules-only path is the reference implementation; model-assisted
behavior must be measured against it and cannot weaken its approval gates.

## 7. Baselines, ablations, and matched resources (MTA-11-09 through MTA-11-11)

Baselines, all using the same frozen consultation inputs, are: (B0) plain SOAP
template with clinician review; (B1) ordinary prompt-based drafting; (B2)
deterministic checks only; (B3) LLM self-critique only; and (B4) deterministic
checks plus optional local verifier, with the same deterministic approval gate.
The full BECCSV treatment is compared to B2 as primary. Ablations remove in
turn: reverse/source coverage, temporal edges, clinical relation edges,
uncertainty/abstention, deterministic rules, and optional local verifier.

Freeze cases, source facts, model/profile digests, prompt and output budgets,
retry/time limits, hardware, concurrency policy, and scoring rules before each
comparison. A missing candidate or failed run stays in the report; it is never
replaced with a simulated success. No model family gets a larger prompt or
retry budget without declaring a separate experiment.

## 8. Development and locked evaluation (MTA-11-12 through MTA-11-14)

Use versioned synthetic scenarios for development. Scenario labels must say
synthetic, and generated values must not be presented as clinical evidence.
After inspecting a development error, add a new case/version; do not edit a
locked case or acceptance label. Keep an immutable development cohort and a
distinct acceptance reservation. The acceptance cohort requires independent
qualified annotators and adjudication; it is currently unavailable, so no
acceptance result can be produced.

Metamorphic tests should change one property at a time: equivalent unit
conversion; faithful paraphrase; clause order; temporal flip; swapped drug and
dose; negation reversal; and subject/speaker swap. Expected behavior is
invariance only for semantics-preserving transformations. Each semantic flip
must change the relevant typed state or produce an abstention; string similarity
alone is not a pass criterion.

## 9. Outcomes and statistical plan (MTA-11-15 through MTA-11-18)

Primary: consultation-level critical unsafe-claim miss rate, with false-alarm
rate, all failure/timeout/abstention denominators, and paired B2-versus-full
BECCSV differences. Secondary: required source omission coverage and note-claim
provenance completeness. Report both raw numerators/denominators and
consultation-clustered 95% intervals. Keep all turns, clips and metamorphic
siblings from one original consultation in the same cluster. Use a paired
consultation bootstrap; for very small cohorts report descriptive exact counts
and intervals only. Never claim significance from 6–12 developer cases.

Predeclared support requires at least 20% relative reduction in critical misses,
false-alarm increase within 5 percentage points, and no increase in catastrophic
error count. The interval criteria from Section 1 must also be met. Qualified
reviewers must approve severity mapping and false-alarm tolerance before
acceptance data are examined. If reviewers are unavailable, outcomes and
thresholds remain a research plan, not a pass.

## 10. Failure, contamination, and reporting rules (MTA-11-19 through MTA-11-22)

Retain negative results, failed/aborted runs, timeouts, malformed output,
resource deferrals, changed dataset digests, and suspected contamination in the
same experiment ledger. Do not drop a difficult case from a denominator after
seeing its result. A novel-method success claim requires passing the frozen
criteria against all named baselines without increased false-block burden; no
such result is currently available.

The paper deliverable is a **systems/method-hypothesis** report with a graph
diagram, algorithm, implementation boundary, preregistered baselines and
ablations, dataset/provenance protocol, metrics, negative results, and
limitations. It must not imply clinical efficacy. Any clinical efficacy claim
requires a later independent, appropriately governed study and separate
authorization.
