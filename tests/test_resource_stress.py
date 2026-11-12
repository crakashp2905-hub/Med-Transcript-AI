from services.resource_stress import run


def test_resource_stress_is_seeded_bounded_and_tears_down():
    seen = []
    report = run(
        lambda randomizer, index: seen.append((index, randomizer.randrange(100))),
        seed=7,
        iterations=20,
    )
    repeat = run(
        lambda randomizer, index: seen.append((index, randomizer.randrange(100))),
        seed=7,
        iterations=20,
    )
    assert report["complete"] and report["teardown"] == "gc_complete"
    assert repeat["completed"] == 20 and report["seed"] == repeat["seed"] == 7
