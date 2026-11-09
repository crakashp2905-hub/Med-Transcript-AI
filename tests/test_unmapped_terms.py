from services.unmapped_terms import map_term


def test_unrecognized_term_stays_unmapped():
    result = map_term('unknownpharmacon')
    assert result['status'] == 'unmapped' and result['concept'] is None
    assert result['certainty'] == 'unknown' and result['requires_review'] is True
