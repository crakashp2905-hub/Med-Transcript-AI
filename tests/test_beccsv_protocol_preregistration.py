from pathlib import Path


def test_beccsv_protocol_freezes_hypothesis_method_and_honest_limits():
    protocol = " ".join(
        Path("docs/research/beccsv-protocol-v1.md").read_text(encoding="utf-8").split()
    )
    required = (
        "## 1. Falsifiable hypothesis",
        "## 2. Method specification",
        "## 3. Difference from simpler checks",
        "## 4. Formal objects, loss, and algorithm",
        "## 5. Abstention policy",
        "## 6. Deterministic-first implementation boundary",
        "## 7. Baselines, ablations, and matched resources",
        "## 9. Outcomes and statistical plan",
        "## 10. Failure, contamination, and reporting rules",
        "at least 20% relative reduction",
        "no more than 5 percentage points",
        "not clinically validated",
        "such result is currently available",
        "plain SOAP template",
        "ordinary prompt-based drafting",
        "deterministic checks only",
        "LLM self-critique only",
        "deterministic checks plus optional local verifier",
        "critical unsafe-claim miss rate",
        "false-alarm rate",
        "source omission coverage",
        "consultation-clustered 95% intervals",
        "paired consultation bootstrap",
        "Never claim significance from 6–12 developer cases",
    )
    assert all(item in protocol for item in required)
