# Dependency SBOM

`services.sbom` emits a network-free CycloneDX-style inventory from the pinned
`constraints-ci.txt`. It records exact component versions and distinguishes an
SBOM from a vulnerability audit: if `pip-audit` or equivalent tooling is absent,
the status remains `not_run_without_tooling`, never “clean.”
