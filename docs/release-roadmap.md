# Release roadmap

The authoritative task count and evidence links are in [the engineering scorecard](engineering-scorecard.md). A passed synthetic walkthrough does not authorize clinical use.

| Track | Next deliverable | Exit evidence | Current constraint |
| --- | --- | --- | --- |
| Offline engineering | Complete the bounded API/data contracts, interruption and retention tests, local diagnostics and reproducible packaging | Exact-source acceptance, complete browser results, migration/restore receipts, no unresolved P0 issue | Missing cached lint/type/coverage/audit tooling, wheelhouse and local container/TLS runtime remain explicit blockers |
| Local research | Diagnose long-conversation ASR, speaker-turn errors and evidence-linked fact/verification failures on the existing development inputs | Frozen protocols, failure-inclusive case results, paired consultation comparisons, negative findings and reproducible ablations | No measured ASR candidate meets the unchanged 5% normalized WER admission gate; diarization and Qwen judgments remain experimental |
| Independent clinical acceptance | Obtain qualified independent review, adjudicate a distinct acceptance cohort and measure real correction workload | Source-audited labels, reviewer qualifications, resolved adjudication, appropriate institutional/privacy/security decisions | No reviewers or institutional owner are available; no synthetic result substitutes for them |
| Optional deployment | Configure a real identity provider, domain, HTTPS endpoint and operational custody | Real provider/configuration checks and controlled deployment evidence | Local simulated Google OIDC is software-test evidence only; no live account activation is implied |
| Future work outside V1 | Consider additional languages, imaging and speech generation under separate requirements | Separate data rights, protocols, clinical scope and safety evaluation | English consultation transcription and supervised note review remain the V1 scope; MRI, X-ray and TTS are not current acceptance requirements |

Prioritize corrupted evidence, identity leakage, missing audit and unsafe approval as P0 blockers. Preserve working manual transcription and deterministic reviewed-fact SOAP while improving local models. Do not promote a model from a short-clip score or a developer-authored challenge set.
