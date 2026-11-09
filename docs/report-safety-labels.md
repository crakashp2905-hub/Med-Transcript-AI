# Developer report safety labels

Before a developer-only report is published or reused, `services.report_safety`
requires explicit false labels for independent clinical gold and real-patient
release (or the equivalent `clinical_acceptance=false` marker). Missing labels
fail closed; they are never inferred from a filename or a model verdict.
