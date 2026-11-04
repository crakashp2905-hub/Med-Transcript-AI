# Dependency audit triage — November 2 failure

Existing GitHub run `41445260398` failed with: `med-transcript-ai: Dependency not found on PyPI and could not be audited: med-transcript-ai (0.4.0)`.

The workflow installs first-party source editable and now uses `pip_audit --strict --skip-editable --format json --output dependency-audit.json`. This excludes the private editable first-party distribution from PyPI identity lookup while retaining strict third-party checks. No vulnerability ID is ignored and audit errors continue to fail the job. The application itself remains subject to source, behavior and security tests.

The local `pip-audit` tool/advisory cache is absent. No package was installed and no fresh advisory query was issued. This is a verified configuration/root-cause triage, **not a fresh clean vulnerability attestation**. Any future hosted audit result must remain separate from offline dependency inventory and cache-age evidence. The baseline records the historical failed run; it is not overwritten by this fix.
