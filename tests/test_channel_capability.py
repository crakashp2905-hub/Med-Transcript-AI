from services.asr.channel_capability import detect


def test_two_channel_path_requires_truthful_hardware_or_file_capability():
    hardware = detect(reported_channels=2, source='hardware')
    fake = detect(reported_channels=2, source='generated')
    assert hardware['two_channel_supported'] is True and hardware['hardware_confirmed'] is True
    assert fake['two_channel_supported'] is False and fake['hardware_confirmed'] is False
    assert hardware['role_assignment'] == 'clinician_confirmation_required'
