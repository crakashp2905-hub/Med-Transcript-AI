from services.perturbation_cases import PERTURBATIONS, cases


def test_perturbation_cases_cover_required_adversarial_variants():
    result = cases("synthetic consultation")
    assert [item["kind"] for item in result] == list(PERTURBATIONS)
    assert all(item["source_untrusted"] for item in result)
