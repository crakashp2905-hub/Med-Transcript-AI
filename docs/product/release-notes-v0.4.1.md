# Release notes — v0.4.1 engineering evidence bundle

**State:** internal prototype snapshot; not a clinical release.
**Source revision:** `ce57190d56ed587cf237d6d008bbd14f0b71648c` (base revision before this planning bundle).
**Data mode:** local synthetic/public-mock evidence only; no paid model calls or real-patient processing.

## Included

- A reproducible offline demo command and scope-labeled runtime support matrix.
- A static, read-only investor showcase with a visible “NOT CLINICALLY APPROVED” notice.
- Architecture, reproducibility, benchmark publication, sample supplement, algorithm reference and engineering-paper draft artifacts.
- Warning review, offline onboarding, demo evidence card, workload sensitivity and human-study protocol planning work.
- This linked product backlog, prioritization rubric, dependency-gated roadmap and technical-debt register.

## Verification boundary

The source snapshot has task-specific local reports and checks recorded in `evaluation/reports/`. Those reports are bound to their own exact source commits; this note does not assert that every historical check was rerun at the base revision. Run the master offline acceptance workflow before presenting a new build as checked.

The current eligible ASR candidates do not satisfy the unchanged 5% normalized-WER admission gate. Synthetic and scripted checks do not establish clinical accuracy, clinician time savings, physical device support, customer demand, EHR certification, security approval, or pilot authorization. Qualified reviewers, hardware identification, and institutional sign-off remain open dependencies.

## Upgrade, rollback and data handling

This is a source/documentation snapshot and defines no production migration. Use only synthetic/public-mock fixtures. Preserve local benchmark inputs and reports; do not introduce patient data. Follow the offline demo runbook for local execution and its stated reset behavior. Any later build must use its own source-bound acceptance receipt.
