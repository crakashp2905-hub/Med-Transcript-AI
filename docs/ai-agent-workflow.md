# AI coding agent workflow

This guide applies to Codex and other coding agents working in the repository. Use it with the root [AGENTS.md](../AGENTS.md), the [offline runbook](demo-runbook-offline.md), and the [benchmark integrity policy](benchmark-integrity.md).

## 1. Establish the baseline before editing

From the repository root:

```powershell
git status --short
git rev-parse HEAD
python -m services.master_ledger
python -m services.status_report
```

Record existing modified/untracked paths. They may be active benchmark work or user changes; do not stage, reset, clean, or overwrite them. The current engineering task ledger is `evaluation/master-task-ledger.json`; the older 247-task scorecard is a separate source and must not be substituted for it.

## 2. Protected acceptance and benchmark material

Treat these inputs as immutable:

- `evaluation/acceptance-reservation-v1.json`
- Every file under `evaluation/annotation-source/acceptance-v1/`, including the blank reviewer packets and qualification registry
- Existing manifests, locks, audio references, gold/annotation schemas, and frozen runs under `evaluation/datasets/` and `evaluation/runs/`
- Existing benchmark, acceptance, clinical challenge, and source-audit reports under `evaluation/reports/`

Do not run ASR, drafting, tuning, prompt selection, or model inference on the reserved groups `day5_consultation05` through `day5_consultation07`. The reserved cohort is for source audit and future qualified, independent human annotation only. The default `services.acceptance_audit.audit()` path can fetch remote LFS pointers; do not run it with its default network behavior. No missing asset may be fetched to make a test pass.

If new evidence is required, write a new versioned report path and preserve all prior files. A report update is not permission to alter its source manifest or reference data.

## 3. Run only the checks relevant to the change

Use the installed environment; do not install packages or update lockfiles as part of test setup. Prefer the output-redacting wrapper for Python tests:

```powershell
python -m services.safe_pytest tests/test_<area>.py
python -m ruff check services/<changed_module>.py tests/test_<area>.py
python -m ruff format --check services/<changed_module>.py tests/test_<area>.py
```

For a frontend-only change, run `npm run build` from `apps/clinician-web` only when the existing local `node_modules` are available. Do not run `npm install`, `npm ci`, or network-backed package commands.

For the model-free workflow check, run `python -m services.offline_demo --self-test`; it creates a fresh isolated synthetic workspace under ignored `data/`. Do not inspect, print, or commit local access keys. Run full offline acceptance only when requested for the task, and always choose a new unique version:

```powershell
python -m services.offline_acceptance --version local-<unique-run-id>
```

That command writes a versioned report and updates `data/offline-acceptance-summary.json` and `docs/offline-acceptance-summary.md`. Check their existing state first; preserve prior evidence and user edits. A failed or blocked check must be recorded as such, never converted into a pass.

## 4. Preserve evidence and update status carefully

- Keep failures, partial outputs, and missing local assets visible. Do not edit a frozen threshold, denominator, reference transcript, or failure policy to make a candidate pass.
- Bind each generated report to its source commit, relevant input hashes, exact test IDs, output hash, environment, and known limitations. Record variable fields when output depends on time, platform, installed packages, random seeds, or runtime state.
- Run `python -m services.master_ledger` before and after changing ledger status. Mark `verified` only when the hash-bound receipt passes at the recorded source commit. Use `implemented` when required external or exact-commit evidence is still absent.
- Stage exact paths with `git add -- <path>`. Never use broad staging when unrelated changes exist. Never use `git clean`, `git reset --hard`, or overwrite protected material to obtain a clean worktree.
- Report what passed, failed, or was blocked and the exact commit. Software tests and synthetic demonstrations do not establish clinical accuracy, clinician benefit, institutional approval, or production readiness.

## 5. Scope boundaries

Use only local tools, models and data already present. No paid calls, hosted inference, downloads, credentials, clinical reviewer identities, patient information, or external validation may be invented or implied. Keep AI proposals distinct from clinician-approved notes and preserve the application’s existing approval and provenance gates.
