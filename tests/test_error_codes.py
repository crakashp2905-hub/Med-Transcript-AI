from services.error_codes import ErrorCode, public_error


def test_error_codes_have_stable_non_sensitive_public_mapping():
    result = public_error(ErrorCode.ASR_FAILED)
    assert result == {'error_code': 'asr_failed', 'message': 'asr failed'}
    assert 'token' not in result['message'] and 'secret' not in result['message']


def test_unknown_error_does_not_echo_input():
    result = public_error('secret-token-and-audio')
    assert result['error_code'] == 'internal_error'
    assert 'secret-token-and-audio' not in str(result)
