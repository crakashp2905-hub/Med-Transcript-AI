# Clinical gold annotation and evaluation

Use the pinned full-consultation manifest as the development source of truth. Preserve every original-timeline turn, uncertain phrase, overlap and speaker uncertainty. Listen to audio before annotating; never derive gold labels from ASR hypotheses or generated notes. Freeze case IDs, audio hashes, transcript version, annotation version, adjudication decisions and reviewer identities before comparisons. Separate consultation groups across development and acceptance; audit speaker/site/device overlap before claiming independence.

Two independently working qualified reviewers should label each atomic assertion and its evidence turn/character span, then resolve disagreements through a third adjudicator. Record medication name, dose value/unit, route, frequency, duration, allergies and reactions, negation, uncertainty, patient/family attribution, current/historical/planned status, anatomical site, laterality, measurements and plans. Missing information stays unknown. Do not turn absence of an allergy mention into “no allergies.” Ambiguous drug/dose references need explicit ambiguity labels and clinician clarification. Keep omissions as errors, including failed processing cases.

Concept annotation objects require nonempty strings `category`, `concept`, `subject`, `assertion`, `temporality`; additional flat scalar slots can hold dose/unit/route/frequency/duration/reaction. `evidence` and `annotation_id` are provenance and excluded from exact matching. Ontology, units and matching rules must be frozen before scoring. Categories should include medication, dose, allergy, negation and other required clinical assertions. The scorer uses multiset matching: wrong doses produce an omission and an insertion, rather than credit for a shared drug name. It reports per-category counts, precision, recall, omissions, insertions, normalized/raw WER and case-insensitive CER. Null denominators remain null. Timestamp union coverage is separately measured and does not prove completeness.

Run independently annotated cases using:

```powershell
.\.venv\Scripts\python.exe -m services.clinical_evaluation --annotated PATH_TO_APPROVED_JSON --output data/clinical-results.json
.\.venv\Scripts\python.exe -m services.clinical_evaluation --adversarial evaluation/clinical-adversarial-v1.json --output evaluation/reports/clinical-adversarial-2026-10-25.json
```

Annotated JSON has `cases`, each with `id`, `reference`, `hypothesis`, `expected` and `observed` concept lists, and optional `failed`. A failed case is scored as empty output. The synthetic adversarial cases test changes to dose, unit, negation, medication/allergen, laterality, temporality, attribution and unsupported diagnoses, plus unchanged controls. These examples were authored by developers; their confusion matrix is regression evidence, not calibrated clinical sensitivity/specificity. An independent clinical challenge set remains a dependency.

Fact extraction currently splits evidence-preserving sentences into typed, unreviewed proposals. Subject, source and unresolved clinical slots stay unknown. Complex conjunctions, pronouns, multi-drug instructions and negation scope need clinician splitting/correction. The separate verifier uses conservative lexical/critical-field rules and can flag valid paraphrases; it is not a clinically validated semantic entailment model. It blocks observed critical contradictions even when a source quote is attached. Neither extractor nor verifier may approve a note.
