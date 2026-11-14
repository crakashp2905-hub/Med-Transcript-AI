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

## Egress-denied test runs

Use `scripts/run_egress_denied_tests.ps1 -Image <preloaded-test-image>` to run
selected tests in a container with Docker `--network none`, a read-only source
mount, a read-only root filesystem, no capabilities, and bounded resources. The
runner only inspects an image already present locally; it never builds or pulls
one. Pre-provision that image and its pinned test dependencies in a separate
connected build lane, then retain its digest with the test result. Container
network isolation is the tested egress boundary; Python socket guards alone
are not treated as a firewall.

For a host-level deny-by-default check, run the lane in a disposable VM or
dedicated runner whose outbound policy blocks DNS and all non-loopback traffic
by default. Add only explicitly required build-time destinations in the
separate provisioning lane, then run tests after those exceptions are removed.
Do not change a shared workstation's global firewall policy for this check.
The project has not applied or independently verified a host firewall policy;
the runner's `--network none` isolation is not evidence of host-level egress
denial.
