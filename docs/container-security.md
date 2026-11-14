# Container security contract

The local Compose contract uses read-only roots, dropped capabilities,
`no-new-privileges`, an internal database network, bounded memory/CPU/PIDs and
loopback binding. Production Google secrets are mounted as Docker secrets, not
environment values. Runtime Docker/TLS hardening remains an operator/CI check;
the static contract does not claim an external security audit.

The application creates its configured audio asset root with POSIX mode `0700`
and new upload objects with mode `0600`, and refuses a symlink at that root.
On Windows, these mode bits do not establish a private ACL: deployment must
restrict the database, asset, export and model-cache directories to the service
identity. The current application does not provision or verify those Windows
ACLs, and path checks do not claim race-free protection from a hostile local
process that can modify the storage directory concurrently.
