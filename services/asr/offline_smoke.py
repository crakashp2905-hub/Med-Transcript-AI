"""Fail-closed real-inference smoke path for the frozen public mock corpus.

Inference is attempted only when the selected local profile's exact digest has
an independently prepared admission record. This command never downloads models.
"""

import argparse
import json
from pathlib import Path

from services.api.ingest import file_sha256
from services.asr.admission import evaluate_candidate_admission
from services.asr.profiles import load_profiles
from services.evaluation import run as run_evaluation


DEFAULT_MANIFEST = Path("evaluation/datasets/primock57-smoke-v1/manifest.json")


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_smoke(
    profiles_path,
    admission_path,
    output_path,
    manifest_path=DEFAULT_MANIFEST,
    profile_id=None,
):
    """Return a no-inference reason, or run the normal failure-inclusive harness."""
    manifest = Path(manifest_path).resolve(strict=True)
    expected = DEFAULT_MANIFEST.resolve(strict=True)
    if manifest != expected:
        raise ValueError("smoke_manifest_must_be_frozen_primock57_public_mock")
    manifest_sha = file_sha256(manifest)
    profiles = load_profiles(profiles_path)
    if admission_path is None:
        profile = profiles.get(profile_id)
        result = {
            "status": "skipped",
            "reason_code": "admission_record_missing",
            "manifest_sha256": manifest_sha,
            "automatic_download": False,
        }
        if profile is not None:
            result.update(
                profile_id=profile.profile_id,
                profile_sha256=profile.sha256,
                local_model_status=profile.availability()["status"],
            )
        return result
    admission = _load_json(admission_path)
    if (
        not isinstance(admission, dict)
        or admission.get("schema_version") != "offline_asr_admission_v1"
    ):
        raise ValueError("invalid_asr_admission_record")
    profile_id = admission.get("profile_id")
    profile = profiles.get(profile_id)
    if profile is None:
        return {
            "status": "skipped",
            "reason_code": "admitted_profile_not_configured",
            "manifest_sha256": manifest_sha,
        }

    evidence = admission.get("evidence")
    decision = evaluate_candidate_admission(profile_id, evidence)
    if admission.get("profile_sha256") != profile.sha256:
        return {
            "status": "skipped",
            "reason_code": "profile_digest_not_admitted",
            "manifest_sha256": manifest_sha,
            "profile_sha256": profile.sha256,
        }
    if admission.get("decision") != decision:
        return {
            "status": "skipped",
            "reason_code": "admission_decision_mismatch",
            "manifest_sha256": manifest_sha,
            "profile_sha256": profile.sha256,
        }
    if decision["status"] != "admitted":
        return {
            "status": "skipped",
            "reason_code": "profile_not_admitted",
            "manifest_sha256": manifest_sha,
            "profile_sha256": profile.sha256,
            "admission": decision,
        }
    if profile.availability()["status"] != "available_not_admitted":
        return {
            "status": "skipped",
            "reason_code": "local_model_unavailable_or_integrity_failed",
            "manifest_sha256": manifest_sha,
            "profile_sha256": profile.sha256,
        }

    report = run_evaluation(manifest, profile, output_path)
    return {
        "status": "completed",
        "manifest_sha256": manifest_sha,
        "profile_sha256": profile.sha256,
        "evaluation": report,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profiles", required=True, help="Local profile JSON; no model downloads"
    )
    parser.add_argument(
        "--profile-id", required=True, help="Explicit local profile to inspect"
    )
    parser.add_argument(
        "--admission", help="Exact profile digest and admission evidence JSON"
    )
    parser.add_argument(
        "--out", required=True, help="New immutable evaluation report path"
    )
    args = parser.parse_args()
    result = run_smoke(
        args.profiles, args.admission, args.out, profile_id=args.profile_id
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
