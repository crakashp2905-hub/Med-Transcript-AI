from services.repro_bundle import build


def test_repro_bundle_has_hashes_commands_and_negative_results():
    value = build('.')
    assert value['model_free'] and value['downloads_attempted'] == 0 and value['paid_calls'] == 0
    assert value['negative_results_preserved'] and len(value['artifacts']) >= 5
    assert value['clinical_release'] == 'BLOCKED_EXTERNAL_EVIDENCE_REQUIRED'
