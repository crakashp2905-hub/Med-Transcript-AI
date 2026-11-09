from services.storage_lifecycle import decide


def test_storage_lifecycle_deletes_only_after_explicit_user_discard():
    assert decide(expired=True, recovery_authorized=True, retained_copy=True, user_discarded=True)['action'] == 'delete'


def test_storage_lifecycle_keeps_authorized_recovery_copy():
    result = decide(expired=True, recovery_authorized=True, retained_copy=True, user_discarded=False)
    assert result['action'] == 'retain' and result['recoverable'] is True
