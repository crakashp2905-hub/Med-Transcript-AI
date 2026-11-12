"""Strict offline mode must fail closed before a hosted call can begin."""

import os
import subprocess
import sys


def test_strict_offline_denies_external_network_and_hosted_modes_in_fresh_process():
    program = """
import os
import socket
import services
from services.offline import OfflineNetworkDenied, validate_profile
from services.review.providers import configured_provider

assert os.environ['MED_TRANSCRIPT_OFFLINE'] == '1'
assert os.environ['HF_HUB_OFFLINE'] == '1'
assert os.environ['TRANSFORMERS_OFFLINE'] == '1'
assert os.environ['HF_HUB_DISABLE_TELEMETRY'] == '1'
for action in (
    lambda: socket.getaddrinfo('example.com', 443),
    lambda: socket.socket().connect(('203.0.113.1', 443)),
):
    try:
        action()
    except OfflineNetworkDenied:
        pass
    else:
        raise AssertionError('external_network_allowed')
assert socket.getaddrinfo('localhost', 8000)
validate_profile()
os.environ['MED_TRANSCRIPT_AUTH_MODE'] = 'google'
try:
    validate_profile()
except ValueError as exc:
    assert str(exc) == 'live_oauth_forbidden_in_strict_offline_mode'
else:
    raise AssertionError('live_oauth_allowed')
os.environ['MED_TRANSCRIPT_AUTH_MODE'] = 'local'
os.environ['MED_TRANSCRIPT_DRAFTING_MODE'] = 'hosted'
for action in (validate_profile, configured_provider):
    try:
        action()
    except ValueError as exc:
        assert str(exc) == 'hosted_inference_forbidden_in_strict_offline_mode'
    else:
        raise AssertionError('hosted_inference_allowed')
"""
    environment = {**os.environ, "STRICT_OFFLINE": "1", "MED_TRANSCRIPT_OFFLINE": "0"}
    environment.pop("MED_TRANSCRIPT_PROFILE", None)
    environment.pop("MED_TRANSCRIPT_AUTH_MODE", None)
    environment.pop("MED_TRANSCRIPT_DRAFTING_MODE", None)
    result = subprocess.run(
        [sys.executable, "-c", program],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
