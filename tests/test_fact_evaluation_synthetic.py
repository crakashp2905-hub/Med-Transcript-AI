from services.clinical_metrics import evaluate


def test_synthetic_fact_evaluation_reports_precision_recall_and_omissions():
    gold = [{'category': 'symptom', 'concept': 'cough', 'subject': 'patient', 'assertion': 'affirmed', 'temporality': 'current'},
            {'category': 'medication', 'concept': 'warfarin', 'subject': 'patient', 'assertion': 'affirmed', 'temporality': 'current'}]
    observed = [gold[0]]
    result = evaluate('Cough; warfarin.', 'Cough.', gold, observed)
    assert result['concept_precision'] == 1.0 and result['concept_recall'] == 0.5
    assert result['concept_omissions'] == 1
    assert result['clinical_adjudication'] == 'not_established_by_automated_metrics'
