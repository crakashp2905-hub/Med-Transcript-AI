from services import domain_contracts as contracts


def test_typed_clinical_boundary_exports_are_present_and_release_safe():
    names = (
        'ClinicalFact', 'TranscriptVersion', 'EvidenceSpan', 'ClaimRelation',
        'VerificationFinding', 'NoteVersion', 'InferenceReceipt', 'Approval',
    )
    assert all(hasattr(contracts, name) for name in names)
    receipt = contracts.InferenceReceipt(status='completed')
    assert receipt.independent_clinical_gold is False
