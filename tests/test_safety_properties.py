import random
from decimal import Decimal
from copy import deepcopy
import pytest
from services.review.clinical import check_claim, atomic_spans
from services.detailed_benchmark import coverage
from tests.test_foundation import setup, headers
from tests.test_review_workflow import prepare, draft, approve


def test_fixed_seed_exact_unit_equivalence_and_critical_unit_changes():
    rng = random.Random(20261104)
    for _ in range(150):
        mg = Decimal(rng.randrange(1, 10000)) / Decimal(10)
        grams = mg / Decimal(1000)
        reference = f"Taking warfarin {grams} g."
        assert check_claim(reference, f"Taking warfarin {mg} mg.") == []
        assert check_claim(reference, f"Taking warfarin {mg} mcg.")


def test_fixed_seed_time_window_coverage_and_source_span_round_trip():
    rng = random.Random(814)
    for _ in range(200):
        duration = rng.randrange(10, 500)
        cuts = sorted({0, duration, *[rng.randrange(duration) for _ in range(20)]})
        intervals = list(zip(cuts, cuts[1:]))
        assert coverage(intervals, duration)
        assert not coverage([(max(1, a), b) for a, b in intervals], duration)
        value = f"Patient denies fever; taking warfarin {rng.randrange(1, 99)} mg daily. No cough."
        spans = list(atomic_spans(value))
        assert all(
            value[a:b] == quote and 0 <= a < b <= len(value) for a, b, quote in spans
        )
        assert all(a2 >= b1 for (_, b1, _), (a2, _, _) in zip(spans, spans[1:]))


@pytest.mark.parametrize(
    "mutation",
    ["review", "critical", "subject", "temporality", "negation", "dose", "evidence"],
)
def test_synthetic_approval_mutations_never_pass_without_their_required_review(
    setup, mutation
):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path, "Patient takes warfarin 0.5 mg daily.")
    original = deepcopy(facts)
    if mutation == "review":
        facts[0]["reviewed"] = False
    elif mutation == "critical":
        facts[0]["critical_reviewed"] = False
    elif mutation == "subject":
        facts[0]["subject"] = "unknown"
    elif mutation == "temporality":
        facts[0]["temporality"] = "unknown"
    elif mutation == "negation":
        facts[0]["text"] = "Patient does not take warfarin 0.5 mg daily."
    elif mutation == "dose":
        facts[0]["text"] = "Patient takes warfarin 5 mg daily."
    else:
        facts[0]["evidence"]["quote"] = "Invented evidence."
        assert (
            client.post(
                f"/v1/encounters/{eid}/drafts",
                headers=headers(),
                json={"transcript_version_id": tx["id"], "facts": facts},
            ).status_code
            == 422
        )
        return
    note = draft(client, eid, tx, facts)["note"]
    assert approve(client, eid, note).status_code == 409
