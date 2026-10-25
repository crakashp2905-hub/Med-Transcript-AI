# Automated checks and recovery

The earlier failed main run [40101909147](https://github.com/crakashp2905-hub/Med-Transcript-AI/actions/runs/40101909147), check 120895629736, did not start a runner. GitHub's annotation states: “The job was not started because recent account payments have failed or your spending limit needs to be increased.” That was an account restriction, not a test failure. New main commit `4060c12` completed [run 40206920869](https://github.com/crakashp2905-hub/Med-Transcript-AI/actions/runs/40206920869) successfully: both Python jobs, frontend, PostgreSQL and container jobs passed. Capacity was available for this run; no billing settings were changed by this agent. If the annotation recurs, the owner must check Billing & plans. Branch protection configuration remains an owner-controlled decision.

`ci.yml` runs Python base and ASR-extra tests, frontend build/audit, PostgreSQL integration, and Docker configuration/build on Ubuntu 24.04. Python 3.13 dependency versions use `constraints-ci.txt`; this records the tested environment, rather than claiming a cross-platform hash lock. Optional packages are not installed just because they appear in constraints. Dependabot opens weekly dependency and workflow updates. The scheduled/manual dependency audit fails on known Python advisories.

The 2026-10-25 local audit found six advisories in pip 25.1.1. Upgrading the environment and CI/container bootstrap to pip 26.2.2 cleared that audit. See `evaluation/reports/dependency-audit-2026-10-25.json`. An empty advisory result is not a security certification.

The editable application distribution itself is not published on PyPI and was skipped by the advisory lookup. Its local metadata still reports an older version; the report is a dependency snapshot, not proof that project source has been security audited.

From a clean clone on Windows:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip==26.2.2
.\.venv\Scripts\python.exe -m pip install -c constraints-ci.txt -e '.[dev,asr,postgres,media]'
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux, replace the first line with `python3.13 -m venv .venv` and the executable with `.venv/bin/python`. The hosted workflow separately tests installation without ASR. Frontend: in `apps/clinician-web`, run `npm ci`, `npm run build`, `npm audit --omit=dev` with Node 22. Never copy a developer's ignored data or credentials into a clean-room installation.

Set `MED_TRANSCRIPT_TEST_POSTGRES` to an isolated disposable PostgreSQL database to run the database integration test. This workstation has no PostgreSQL/Docker service: that test skips locally. The hosted PostgreSQL integration and container build both passed in run 40206920869. Do not point tests at clinical storage.

`model-inference.yml` is manual only and uses the `med-transcript-models` self-hosted runner label. An operator must provision the approved runtime, model files and `data/asr-smoke-profiles.json`; normal PR jobs do not download weights. Runner registration and credentials remain owner dependencies. Review the workflow before enabling it on a runner with secrets; do not allow untrusted fork code on that runner.
