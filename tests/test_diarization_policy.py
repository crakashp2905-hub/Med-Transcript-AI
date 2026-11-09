from services.diarization_policy import admission


def test_diarization_remains_experimental_without_both_gates():
    result = admission(score=.2, maximum_der=.3, human_review_complete=False)
    assert result['status'] == 'experimental_only'
    assert result['automatic_role_promotion'] is False


def test_diarization_can_only_enter_experimental_review_after_gates():
    result = admission(score=.2, maximum_der=.3, human_review_complete=True)
    assert result['status'] == 'eligible_for_experimental_review'
    assert result['clinical_acceptance'] is False
