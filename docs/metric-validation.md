# Benchmark arithmetic validation

Before a saved benchmark is used, `services/metric_validation.py` checks that
edit counts and reference-word denominators are nonnegative, WER equals the
exact ratio (or is null for a zero-reference case), failures do not exceed the
sample denominator, and input hash mismatches fail closed. A report with failed
samples remains incomplete even when its arithmetic is internally consistent.
