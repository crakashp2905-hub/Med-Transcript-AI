# Synthetic scale and resource-stress checks

The local scale test seeds 1,000 synthetic encounters and checks the version
history indexes plus a bounded `LIMIT 100` history query. The resource harness
uses a fixed seed, bounded iteration/timeout limits, records each failure and
forces teardown cleanup. These are deterministic storage and safety checks, not
production capacity or clinical throughput claims; PostgreSQL/container stress
requires its own provisioned environment.
