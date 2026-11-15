import hashlib
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from services.api.main import Identity, create_app
from services.asr.profiles import ASRProfile


def make_profile(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    contents = {
        "model.bin": b"local synthetic model marker",
        "config.json": b"{}",
        "tokenizer.json": b"{}",
    }
    artifacts = {}
    for name, content in contents.items():
        (model_dir / name).write_bytes(content)
        artifacts[name] = hashlib.sha256(content).hexdigest()
    return ASRProfile(
        profile_id="local-readiness-test",
        model_dir=str(model_dir.resolve()),
        source="synthetic test marker",
        revision="0" * 40,
        license_id="test-only",
        artifacts=artifacts,
    )


def test_model_readiness_reports_integrity_without_loading_or_inference(tmp_path):
    profile = make_profile(tmp_path)
    clinician = Identity(tenant_id=uuid4(), clinician_id=uuid4())
    app = create_app(
        str(tmp_path / "db.sqlite3"),
        {"a" * 40: clinician},
        asr_profiles={profile.profile_id: profile},
    )
    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == "/v1/asr-profiles/{profile_id}/readiness"
    )

    result = route.endpoint(profile.profile_id, actor=clinician)
    assert result["status"] == "available_not_admitted"
    assert result["automatic_download"] is False
    assert result["inference_executed"] is False
    assert result["model_loaded"] is False
    assert result["clinical_validation"] == "not_validated"

    viewer = Identity(tenant_id=uuid4(), clinician_id=uuid4(), role="viewer")
    with pytest.raises(HTTPException) as denied:
        route.endpoint(profile.profile_id, actor=viewer)
    assert denied.value.status_code == 403

    with pytest.raises(HTTPException) as missing:
        route.endpoint("unknown", actor=clinician)
    assert missing.value.status_code == 404

    (tmp_path / "model" / "config.json").write_text("tampered")
    failed = route.endpoint(profile.profile_id, actor=clinician)
    assert failed["status"] == "integrity_failed"
    assert failed["reason_code"] == "model_integrity_failure"
