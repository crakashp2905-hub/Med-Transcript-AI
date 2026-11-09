from services.device_profile import profile


def test_reference_device_profile_does_not_assume_gpu_or_cloud():
    value = profile()
    assert value['id'] == 'single_cpu_16gb' and value['memory_gb'] == 16
    assert value['gpu'] == 'not_required_not_assumed' and value['network'] == 'offline'
    assert value['real_patient_release_authorized'] is False
