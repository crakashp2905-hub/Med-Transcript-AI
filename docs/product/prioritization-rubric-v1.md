# Product prioritization rubric v1

This is an engineering triage rubric for the prototype. It is not a market score, clinical risk assessment, or validated measure of user value.

## Decision order

1. **Safety and integrity gate:** source corruption, critical clinical misstatement, privacy exposure, or approval bypass is P0 and blocks release progression until controlled.
2. **Evidence gate:** work needed to measure a decision-critical unknown (ASR, medication/negation, speaker role, independent verification) precedes convenience work.
3. **Dependency gate:** tasks requiring reviewers, hardware, institutional owners, credentials, or a receiver sandbox remain visible and blocked; do not score them as complete.
4. **Usability and operations:** workflow friction, latency, supportability and integrations follow safety/evidence dependencies.

## Per-item rubric

| Dimension | Rating | Meaning |
|---|---|---|
| Potential impact | High / medium / low | Consequence if the issue is real, based on documented failure mode; not an estimate of frequency. |
| Evidence confidence | Observed / reproducible software case / hypothesis | Strength and source of evidence. Synthetic evidence remains a software case. |
| Dependency | Available / internal work / external owner or asset | Whether work can proceed with current local inputs. |
| Effort | S / M / L / unknown | Relative implementation size; unknown until scoped. |
| Priority | P0 / P1 / P2 | Safety/integrity, evidence, and dependency ordering above. |

Do not combine these into a precise numeric score: frequencies, clinical severity calibration, customer value, and effort estimates lack validated inputs. Record the rationale and acceptance evidence instead. The backlog uses this rubric.
