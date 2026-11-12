"""Strict manifest and receipt contract for offline ASR evaluation runs."""

import re
import hashlib

from services.canonical import content_sha256


SHA256 = re.compile(r"^[a-f0-9]{64}$")
NORMALIZATION_POLICY = "lowercase_words_preserve_decimals_units_negation_v1"
FAILURE_POLICY = "empty_hypothesis_full_reference_deletions"
NORMALIZATION_PATTERN = r"\d+(?:\.\d+)?|[a-z]+(?:['-][a-z]+)*"


def _reference_word_count(text):
    return len(re.findall(NORMALIZATION_PATTERN, text.lower()))


def validate_manifest(manifest):
    """Reject incomplete or malformed evaluation cohorts before any inference."""
    if not isinstance(manifest, dict):
        raise ValueError("invalid_evaluation_manifest")
    if (
        not isinstance(manifest.get("dataset_id"), str)
        or not manifest["dataset_id"].strip()
        or not isinstance(manifest.get("split_role"), str)
        or not manifest["split_role"].strip()
        or manifest.get("data_class") not in ("synthetic", "approved_public")
        or manifest.get("rights_reviewed") is not True
        or not isinstance(manifest.get("license_id"), str)
        or not manifest["license_id"].strip()
        or not isinstance(manifest.get("source_revision"), str)
        or re.fullmatch(r"[a-f0-9]{40}", manifest["source_revision"]) is None
    ):
        raise ValueError("incomplete_evaluation_manifest")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples or len(samples) > 10000:
        raise ValueError("invalid_evaluation_samples")

    seen = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("invalid_evaluation_sample")
        sample_id = sample.get("sample_id")
        group_id = sample.get("group_id")
        if (
            not isinstance(sample_id, str)
            or not sample_id.strip()
            or sample_id in seen
            or not isinstance(group_id, str)
            or not group_id.strip()
            or sample.get("language") != "en"
            or not isinstance(sample.get("audio"), str)
            or not sample["audio"].strip()
            or not isinstance(sample.get("reference"), str)
            or not isinstance(sample.get("audio_sha256"), str)
            or SHA256.fullmatch(sample["audio_sha256"]) is None
        ):
            raise ValueError("incomplete_evaluation_sample")
        role = sample.get("speaker_role", "unknown")
        if role not in ("doctor", "clinician", "patient", "unknown"):
            raise ValueError("invalid_reference_role")
        channel_map = sample.get("channel_map")
        if channel_map is not None and (
            not isinstance(channel_map, list)
            or not channel_map
            or any(
                not isinstance(row, dict)
                or row.get("channel_index") != index
                or row.get("role") not in ("doctor", "clinician", "patient", "unknown")
                for index, row in enumerate(channel_map)
            )
        ):
            raise ValueError("invalid_declared_channel_map")
        try:
            sample["reference"].encode("utf-8")
        except UnicodeError:
            raise ValueError("invalid_reference_encoding") from None
        seen.add(sample_id)
    return samples


def observed_channel_map(sample, channel_count):
    """Preserve only declared source-role mapping; otherwise keep roles unknown."""
    declared = sample.get("channel_map")
    allowed_roles = {"doctor", "clinician", "patient", "unknown"}
    if declared is not None:
        if (
            not isinstance(declared, list)
            or len(declared) != channel_count
            or any(
                not isinstance(row, dict)
                or row.get("channel_index") != index
                or row.get("role") not in allowed_roles
                for index, row in enumerate(declared)
            )
        ):
            raise ValueError("invalid_declared_channel_map")
        return [
            {
                "channel_index": row["channel_index"],
                "role": row["role"],
                "role_source": "manifest_channel_map",
            }
            for row in declared
        ]
    if channel_count == 1:
        role = sample.get("speaker_role", "unknown")
        return [
            {
                "channel_index": 0,
                "role": role,
                "role_source": "reference_role_annotation"
                if role != "unknown"
                else "unknown",
            }
        ]
    return [
        {"channel_index": index, "role": "unknown", "role_source": "unmapped"}
        for index in range(channel_count)
    ]


def make_contract(*, manifest, manifest_sha256, profile, recordings):
    samples = validate_manifest(manifest)
    sample_by_id = {sample["sample_id"]: sample for sample in samples}
    if len(recordings) != len(samples):
        raise ValueError("incomplete_evaluation_run")
    for row in recordings:
        sample = sample_by_id.get(row.get("sample_id"))
        if (
            sample is None
            or row.get("group_id") != sample["group_id"]
            or row.get("audio_path") != sample["audio"]
            or row.get("audio_sha256") != sample["audio_sha256"]
            or row.get("reference_sha256")
            != hashlib.sha256(sample["reference"].encode("utf-8")).hexdigest()
            or row.get("reference_words") != _reference_word_count(sample["reference"])
        ):
            raise ValueError("evaluation_recording_manifest_mismatch")
    decoder = {
        "engine": profile.engine,
        "runtime_version": profile.runtime_version,
        "language": "en",
        "task": "transcribe",
        "beam_size": profile.beam_size,
        "temperature": 0.0,
        "vad_filter": False,
        "word_timestamps": False,
        "condition_on_previous_text": False,
    }
    contract = {
        "schema_version": "offline_asr_evaluation_contract_v1",
        "dataset_id": manifest["dataset_id"],
        "split_role": manifest["split_role"],
        "source_revision": manifest["source_revision"],
        "data_class": manifest["data_class"],
        "license_id": manifest["license_id"],
        "rights_reviewed": manifest["rights_reviewed"],
        "manifest_sha256": manifest_sha256,
        "recordings": recordings,
        "model": {
            "profile_id": profile.profile_id,
            "revision": profile.revision,
            "profile_sha256": profile.sha256,
        },
        "decoder": {**decoder, "configuration_sha256": content_sha256(decoder)},
        "normalization": {
            "policy": NORMALIZATION_POLICY,
            "policy_sha256": content_sha256(
                {
                    "policy": NORMALIZATION_POLICY,
                    "token_pattern": NORMALIZATION_PATTERN,
                    "case": "lower",
                }
            ),
        },
        "denominator": {
            "sample_count": len(recordings),
            "reference_words": sum(r["reference_words"] for r in recordings),
            "failed_samples": sum(r["status"] == "failed" for r in recordings),
            "failure_policy": FAILURE_POLICY,
            "includes_every_predeclared_reference": True,
        },
    }
    contract["contract_sha256"] = content_sha256(contract)
    validate_contract(contract)
    return contract


def validate_contract(contract):
    """Validate that the receipt accounts for every source and denominator."""
    if not isinstance(contract, dict) or contract.get("schema_version") != (
        "offline_asr_evaluation_contract_v1"
    ):
        raise ValueError("invalid_evaluation_contract")
    if any(
        not isinstance(contract.get(key), str) or not contract[key].strip()
        for key in ("dataset_id", "split_role")
    ):
        raise ValueError("incomplete_evaluation_contract")
    if SHA256.fullmatch(contract.get("manifest_sha256", "")) is None:
        raise ValueError("invalid_manifest_digest")
    if (
        not isinstance(contract.get("source_revision"), str)
        or re.fullmatch(r"[a-f0-9]{40}", contract["source_revision"]) is None
        or contract.get("data_class") not in ("synthetic", "approved_public")
        or not isinstance(contract.get("license_id"), str)
        or not contract["license_id"].strip()
        or contract.get("rights_reviewed") is not True
    ):
        raise ValueError("incomplete_dataset_provenance")

    model = contract.get("model")
    if (
        not isinstance(model, dict)
        or not all(
            isinstance(model.get(key), str) and model[key].strip()
            for key in ("profile_id", "revision")
        )
        or SHA256.fullmatch(model.get("profile_sha256", "")) is None
    ):
        raise ValueError("incomplete_model_revision")

    decoder = contract.get("decoder")
    if (
        not isinstance(decoder, dict)
        or SHA256.fullmatch(decoder.get("configuration_sha256", "")) is None
        or decoder.get("language") != "en"
        or decoder.get("task") != "transcribe"
        or decoder.get("configuration_sha256")
        != content_sha256(
            {
                key: value
                for key, value in decoder.items()
                if key != "configuration_sha256"
            }
        )
    ):
        raise ValueError("incomplete_decoder_configuration")
    normalization = contract.get("normalization")
    if (
        not isinstance(normalization, dict)
        or normalization.get("policy") != NORMALIZATION_POLICY
        or normalization.get("policy_sha256")
        != content_sha256(
            {
                "policy": NORMALIZATION_POLICY,
                "token_pattern": NORMALIZATION_PATTERN,
                "case": "lower",
            }
        )
    ):
        raise ValueError("invalid_normalization_policy")

    recordings = contract.get("recordings")
    if not isinstance(recordings, list) or not recordings:
        raise ValueError("missing_recording_receipts")
    ids, reference_total, failed_total = set(), 0, 0
    for row in recordings:
        if not isinstance(row, dict):
            raise ValueError("invalid_recording_receipt")
        if (
            not isinstance(row.get("sample_id"), str)
            or not row["sample_id"].strip()
            or row["sample_id"] in ids
            or not isinstance(row.get("group_id"), str)
            or not row["group_id"].strip()
            or not isinstance(row.get("audio_path"), str)
            or not row["audio_path"].strip()
            or SHA256.fullmatch(row.get("audio_sha256", "")) is None
            or SHA256.fullmatch(row.get("reference_sha256", "")) is None
            or type(row.get("reference_words")) is not int
            or row["reference_words"] < 0
            or row.get("status") not in ("completed", "failed")
            or type(row.get("audio_integrity_verified")) is not bool
            or row.get("status") == "completed"
            and not row["audio_integrity_verified"]
        ):
            raise ValueError("incomplete_recording_receipt")
        channels = row.get("channel_count")
        channel_map = row.get("channel_map")
        if channels is not None and (
            type(channels) is not int or not 1 <= channels <= 8
        ):
            raise ValueError("invalid_channel_count")
        if not isinstance(channel_map, list) or (
            channels is not None and len(channel_map) != channels
        ):
            raise ValueError("incomplete_channel_map")
        if any(
            not isinstance(item, dict)
            or item.get("channel_index") != index
            or item.get("role") not in ("doctor", "clinician", "patient", "unknown")
            or not isinstance(item.get("role_source"), str)
            for index, item in enumerate(channel_map)
        ):
            raise ValueError("invalid_channel_map")
        if row["status"] == "failed":
            failed_total += 1
        reference_total += row["reference_words"]
        ids.add(row["sample_id"])

    denominator = contract.get("denominator")
    if (
        not isinstance(denominator, dict)
        or denominator.get("sample_count") != len(recordings)
        or denominator.get("reference_words") != reference_total
        or denominator.get("failed_samples") != failed_total
        or denominator.get("failure_policy") != FAILURE_POLICY
        or denominator.get("includes_every_predeclared_reference") is not True
    ):
        raise ValueError("failure_inclusive_denominator_mismatch")
    unsigned = {
        key: value for key, value in contract.items() if key != "contract_sha256"
    }
    if contract.get("contract_sha256") != content_sha256(unsigned):
        raise ValueError("evaluation_contract_digest_mismatch")
    return True
