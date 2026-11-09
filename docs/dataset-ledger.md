# Dataset source-of-truth ledger

`evaluation/reports/dataset-ledger-v1.json` records each committed manifest's
license, source revision, protocol hash, split role, grouping rule,
transformation description and source count. The 118-clip, three-consultation
and paired clean/distracted cohorts remain separate. Paired conditions share
consultation groups and are not treated as mutually independent subjects.

Metric replay records separate canonical hashes for references and hypotheses
before scoring; changing either input changes the corresponding digest. This
ledger contains public/synthetic development data only and does not establish
clinical acceptance.
