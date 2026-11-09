# Artifact reporting contract

Offline acceptance and engineering commands retain a versioned JSON receipt.
`services.artifact_summary` renders a human-readable summary with failures and
blocks first, followed by passing checks. The summary always repeats the
clinical-release block and never turns a missing tool into a pass.
