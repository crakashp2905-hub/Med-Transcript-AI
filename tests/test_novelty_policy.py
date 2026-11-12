from services.novelty_policy import classify


def test_novelty_stays_hypothesis_without_distinct_fair_ablation():
    assert (
        classify(
            "evidence graph",
            distinct_algorithm=True,
            fair_ablation=False,
            improvement=True,
        )["label"]
        == "hypothesis"
    )
    assert (
        classify(
            "evidence graph",
            distinct_algorithm=True,
            fair_ablation=True,
            improvement=False,
        )["label"]
        == "hypothesis"
    )
    assert (
        classify(
            "evidence graph",
            distinct_algorithm=True,
            fair_ablation=True,
            improvement=True,
        )["label"]
        == "supported_development_result"
    )
