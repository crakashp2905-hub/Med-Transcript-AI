# Anonymous sample-level ASR supplement

Dataset: `primock57-20consultations-120clips-v1`; 118 public mock samples; 20 consultation clusters; 7 local candidates.

Failure policy: `empty_hypothesis_full_reference_deletions`. Failed outputs receive full-reference deletions; observed failed rows: 0.

The CSV contains pseudonymous row/consultation IDs, speaker role, candidate, edit count, reference-word denominator, and failure state. It contains no transcript strings or original sample IDs. Clinical-critical taxonomy categories are listed for future adjudication but have no scores. These public mock data do not establish privacy for real patient data or clinical acceptance.
