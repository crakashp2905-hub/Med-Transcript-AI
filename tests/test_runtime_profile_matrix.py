import hashlib
import json
from pathlib import Path

from services.asr.profiles import load_runtime_profiles


def test_runtime_profile_matrix_binds_local_cpu_profile_and_unavailable_devices():
    matrix_path = Path("evaluation/contracts/asr-runtime-profiles-v1.json")
    profile_path = Path("data/small-cpu-int8-v1-profiles.json")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    cpu, apple, nvidia = matrix["profiles"]

    assert (
        hashlib.sha256(profile_path.read_bytes()).hexdigest()
        == matrix["reproducibility"]["profile_manifest_sha256"]
    )
    loaded = load_runtime_profiles(profile_path)[cpu["model_profile_id"]]
    assert loaded.sha256 == cpu["model_profile_sha256"]
    assert loaded.device == "cpu" and loaded.compute_type == "int8"
    assert loaded.cpu_threads == 4 and loaded.beam_size == 5
    assert cpu["automatic_download"] is False
    assert cpu["runtime_admission"].startswith("profile_manifest_allowlisted")
    assert apple["status"] == nvidia["status"] == "not_available_on_observed_host"
    assert apple["runtime_profile"] is nvidia["runtime_profile"] is None
