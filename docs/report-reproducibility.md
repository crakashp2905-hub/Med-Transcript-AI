# Generated report reproducibility

`python -m services.report_reproducibility` inventories versioned research and product outputs with each artifact's SHA-256, source commit, generator, input scope, and reproducibility rule. The machine-readable output is `evaluation/reports/report-reproducibility-v1.json`.

## Reproduction rules

- Frozen-input generators for the publication tables, sample supplement, algorithm reference, claim provenance and model cards are required to produce byte-identical output at the same source commit with unchanged source files and input reports. Focused tests call these generators twice and compare their full payloads.
- Runtime snapshots such as the SBOM, license register and read-only readiness CLI preserve the output version and exact output digest. The SBOM records the generation timestamp and installed Python distribution snapshot; the readiness output records local mode, source revision, model directories and evidence state. Cross-environment differences are expected and are listed in the manifest.
- Do not overwrite frozen benchmark, acceptance, or report artifacts. Produce a new version path and record its generator inputs, source revision and output hash.
- A change to an input report, dataset manifest, model registry, runtime, source commit or local package inventory must produce a new versioned output or fail the relevant hash checks.

The manifest covers the listed report generators and snapshots, not every runtime log or temporary test artifact. Reproducible output does not prove clinical validity, correct licensing, security certification or release authorization.
