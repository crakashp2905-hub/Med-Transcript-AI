# Model and fixture licensing policy

The checked-in model registry and [candidate access audit](../evaluation/candidate-access-audit.json)
record the repository revision, license metadata, gate state and artifact size
for every considered ASR candidate. Public metadata is not a grant of rights;
gated or `other` licenses remain blocked until an owner performs a separate
terms review.

Model weights are never redistributed by this repository. The `.gitignore`
rules exclude `models/`, `data/` and runtime caches. Operators must provision
approved artifacts locally, retain their original license notices, and record
the exact digest before evaluation. Synthetic fixtures carry their own license
files and are not patient data. Reports preserve failures and do not imply that
a license or model admission establishes clinical accuracy.
