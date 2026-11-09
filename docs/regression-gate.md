# Pairwise safety regression gate

`services/regression_gate.py` compares two results on the same frozen dataset.
It retains normalized WER plus critical misses, omissions and false blocks. A
lower WER never clears a rise in a safety metric: any safety regression returns
`promotion=blocked`. Missing metrics or changed dataset IDs fail closed. The
gate is a synthetic/development invariant and cannot authorize clinical use.
