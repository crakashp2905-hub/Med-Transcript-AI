# Local performance accounting

`services/local_cost.py` computes a successful-consultation electricity estimate
from measured CPU-seconds, a measured resource trace, CPU watts and an explicit
operator-supplied electricity rate. Memory and disk residency are retained as
measured quantities; hardware market pricing stays unknown unless a separately
audited price model is supplied. Failed or unavailable stages produce an
unknown consultation cost rather than a zero.

`services/latency_targets.py` defines development targets for a single-CPU
16-GB reference device and a developer laptop. Each stage is reported as
`succeeded`, `failed`, `unavailable` or `not_started`. Only a measured successful
stage can meet a target; missing measurements never become fabricated fast
results. These targets are engineering hypotheses, not clinician productivity
or clinical performance claims.
