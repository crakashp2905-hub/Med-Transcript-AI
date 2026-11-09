"""Declared local development device profile; no hardware is inferred."""


REFERENCE_PROFILE = {
    'id': 'single_cpu_16gb', 'cpu': 'x86_64 4+ threads', 'memory_gb': 16,
    'gpu': 'not_required_not_assumed', 'network': 'offline', 'os': 'Windows/Linux',
    'model_policy': 'use already provisioned local artifacts only',
}


def profile():
    return {**REFERENCE_PROFILE, 'real_patient_release_authorized': False}
