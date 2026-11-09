# Automated test lanes

The repository keeps independent lanes for backend unit/integration tests,
security/offline safety checks, optional ASR dependencies, frontend TypeScript
build/audit, PostgreSQL integration, container configuration/build, and the
manual heavyweight model lane. The lanes use synthetic/public fixtures and
preserve missing-runtime skips or failures; a green offline lane never implies
clinical accuracy.

The authoritative definitions are `.github/workflows/ci.yml`,
`.github/workflows/dependency-audit.yml` and
`.github/workflows/model-inference.yml`.
