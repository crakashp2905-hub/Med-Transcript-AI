# Reproducibility appendix outline

- **Method:** deterministic baseline, relation/evidence graph, optional local verifier.
- **Experimental protocol:** frozen cases, identical prompts and inputs, exact denominators, 5% normalized-WER gate.
- **Limitations:** synthetic and development evidence are not clinical sensitivity evidence; missing models and hardware remain explicit blockers.
- **Failure taxonomy:** omissions, false claims, abstentions, malformed outputs, timeout, timestamp and provenance failures.
- **Artifacts:** model/config digests, source hashes, test names, scorecard, and preserved failures.
