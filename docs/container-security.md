# Container security contract

The local Compose contract uses read-only roots, dropped capabilities,
`no-new-privileges`, an internal database network, bounded memory/CPU/PIDs and
loopback binding. Production Google secrets are mounted as Docker secrets, not
environment values. Runtime Docker/TLS hardening remains an operator/CI check;
the static contract does not claim an external security audit.
