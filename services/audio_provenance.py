"""Hash-bound lineage receipts for source and derived PCM audio assets."""

import hashlib
import json
import math
import wave
from pathlib import Path


SCHEMA_VERSION = "audio_lineage_v1"


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _wav_descriptor(path):
    try:
        with wave.open(str(path), "rb") as audio:
            return {
                "container": "wav",
                "encoding": "pcm_s16le" if audio.getsampwidth() == 2 else "pcm_other",
                "channels": audio.getnchannels(),
                "sample_rate": audio.getframerate(),
                "frames": audio.getnframes(),
                "duration_seconds": audio.getnframes() / audio.getframerate(),
            }
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        return {"container": "unknown", "encoding": "unknown"}


def _seal(receipt):
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    return receipt


def source_provenance_from_digest(asset_sha256, descriptor, media_type="unknown"):
    """Create a source receipt when immutable source bytes are held in memory."""
    if len(asset_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in asset_sha256
    ):
        raise ValueError("invalid_audio_asset_digest")
    operation = {
        "operation": "source_asset_capture_v1",
        "media_type": media_type,
    }
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "asset_sha256": asset_sha256,
        "asset": descriptor,
        "parent": None,
        "parent_sha256": None,
        "transformation_manifest": operation,
        "transformation_manifest_sha256": _canonical_sha256(operation),
        "timeline_mapping": {
            "kind": "source_timeline_origin",
            "status": "root_coordinate_system",
            "source_sample_rate": descriptor.get("sample_rate"),
            "source_frame_origin": 0 if descriptor.get("frames") is not None else None,
            "meaning": "Times are measured from the beginning of these exact source bytes.",
        },
    }
    return _seal(receipt)


def source_provenance(path, media_type=None):
    """Describe immutable input bytes and their native timeline origin."""
    path = Path(path)
    descriptor = _wav_descriptor(path)
    return source_provenance_from_digest(
        file_sha256(path),
        descriptor,
        media_type or ("audio/wav" if descriptor["container"] == "wav" else "unknown"),
    )


def validate_provenance(receipt):
    if not isinstance(receipt, dict) or receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid_audio_provenance_schema")
    asset_sha = receipt.get("asset_sha256", "")
    if len(asset_sha) != 64 or any(c not in "0123456789abcdef" for c in asset_sha):
        raise ValueError("invalid_audio_asset_digest")
    operation = receipt.get("transformation_manifest")
    if not isinstance(operation, dict) or receipt.get(
        "transformation_manifest_sha256"
    ) != _canonical_sha256(operation):
        raise ValueError("audio_transformation_manifest_digest_mismatch")
    timeline = receipt.get("timeline_mapping")
    if (
        not isinstance(timeline, dict)
        or not timeline.get("kind")
        or not timeline.get("status")
    ):
        raise ValueError("audio_timeline_mapping_required")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if receipt.get("receipt_sha256") != _canonical_sha256(unsigned):
        raise ValueError("audio_provenance_receipt_digest_mismatch")
    parent = receipt.get("parent")
    if parent is None:
        if receipt.get("parent_sha256") is not None:
            raise ValueError("source_audio_cannot_have_parent_digest")
    else:
        validate_provenance(parent)
        if receipt.get("parent_sha256") != parent["asset_sha256"]:
            raise ValueError("audio_parent_digest_mismatch")
    additional_parents = receipt.get("additional_parents", [])
    if not isinstance(additional_parents, list) or receipt.get(
        "additional_parent_sha256s", []
    ) != [item.get("asset_sha256") for item in additional_parents]:
        raise ValueError("audio_additional_parent_digest_mismatch")
    for additional_parent in additional_parents:
        validate_provenance(additional_parent)
    return True


def derive_provenance(
    parent, output_path, operation, parameters, timeline_mapping, additional_parents=()
):
    validate_provenance(parent)
    additional_parents = list(additional_parents)
    for additional_parent in additional_parents:
        validate_provenance(additional_parent)
    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("audio_operation_name_required")
    if not isinstance(parameters, dict) or not isinstance(timeline_mapping, dict):
        raise ValueError("audio_transform_manifest_and_timeline_required")
    if not timeline_mapping.get("kind") or not timeline_mapping.get("status"):
        raise ValueError("audio_timeline_mapping_required")
    output_path = Path(output_path)
    transformation = {
        "operation": operation,
        "parameters": parameters,
    }
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "asset_sha256": file_sha256(output_path),
        "asset": _wav_descriptor(output_path),
        "parent": parent,
        "parent_sha256": parent["asset_sha256"],
        "additional_parents": additional_parents,
        "additional_parent_sha256s": [
            item["asset_sha256"] for item in additional_parents
        ],
        "transformation_manifest": transformation,
        "transformation_manifest_sha256": _canonical_sha256(transformation),
        "timeline_mapping": timeline_mapping,
    }
    return _seal(receipt)


def crop_timeline(start_frame, end_frame, sample_rate):
    if (
        type(start_frame) is not int
        or type(end_frame) is not int
        or type(sample_rate) is not int
        or not 0 <= start_frame < end_frame
        or sample_rate <= 0
    ):
        raise ValueError("invalid_audio_crop_timeline")
    return {
        "kind": "sample_index_offset",
        "status": "exact_pcm_frame_mapping",
        "parent_sample_rate": sample_rate,
        "output_sample_rate": sample_rate,
        "parent_start_frame": start_frame,
        "parent_end_frame_exclusive": end_frame,
        "formula": "parent_frame = output_frame + parent_start_frame",
        "start_time_ms": start_frame * 1000 / sample_rate,
        "end_time_ms": end_frame * 1000 / sample_rate,
        "maximum_mapping_error_ms": 1000 / sample_rate,
    }


def channel_timeline(channel_index, channel_count, sample_rate, frames):
    if (
        type(channel_index) is not int
        or type(channel_count) is not int
        or type(sample_rate) is not int
        or type(frames) is not int
        or not 0 <= channel_index < channel_count
        or channel_count < 1
        or sample_rate <= 0
        or frames <= 0
    ):
        raise ValueError("invalid_audio_channel_timeline")
    return {
        "kind": "shared_sample_index_timeline",
        "status": "exact_pcm_frame_mapping",
        "parent_sample_rate": sample_rate,
        "output_sample_rate": sample_rate,
        "parent_frames": frames,
        "output_frames": frames,
        "channel_index": channel_index,
        "channel_count": channel_count,
        "formula": "parent_frame = output_frame; channel = channel_index",
        "maximum_mapping_error_ms": 1000 / sample_rate,
    }


def normalization_timeline(
    parent_sample_rate,
    output_sample_rate,
    source_origin_ms=None,
    resampler_group_delay_frames=None,
):
    if (
        type(output_sample_rate) is not int
        or output_sample_rate <= 0
        or parent_sample_rate is not None
        and (type(parent_sample_rate) is not int or parent_sample_rate <= 0)
        or resampler_group_delay_frames is not None
        and (
            type(resampler_group_delay_frames) not in (int, float)
            or not math.isfinite(resampler_group_delay_frames)
        )
    ):
        raise ValueError("invalid_audio_normalization_timeline")
    measured = resampler_group_delay_frames is not None
    return {
        "kind": "resampled_time_scale",
        "status": "measured_delay_mapping"
        if measured
        else "source_origin_or_resampler_delay_unverified",
        "parent_sample_rate": parent_sample_rate,
        "output_sample_rate": output_sample_rate,
        "source_origin_ms": source_origin_ms,
        "resampler_group_delay_frames": resampler_group_delay_frames,
        "delay_units": "output_sample_frames",
        "formula": (
            "source_time_ms = source_origin_ms + (output_frame - resampler_group_delay_frames) * 1000 / output_sample_rate"
            if measured
            else "source_time_ms = unknown; resampler group delay has not been measured"
        ),
        "maximum_mapping_error_ms": (500 / output_sample_rate if measured else None),
    }


def map_output_frame_to_source_ms(output_frame, timeline_mapping):
    """Map a resampled output frame only when origin and delay are evidenced."""
    if (
        type(output_frame) is not int
        or output_frame < 0
        or not isinstance(timeline_mapping, dict)
        or timeline_mapping.get("kind") != "resampled_time_scale"
        or timeline_mapping.get("status") != "measured_delay_mapping"
    ):
        raise ValueError("measured_resampler_timeline_required")
    rate = timeline_mapping.get("output_sample_rate")
    origin = timeline_mapping.get("source_origin_ms")
    delay = timeline_mapping.get("resampler_group_delay_frames")
    if (
        type(rate) is not int
        or rate <= 0
        or type(origin) not in (int, float)
        or not math.isfinite(origin)
        or type(delay) not in (int, float)
        or not math.isfinite(delay)
    ):
        raise ValueError("incomplete_resampler_timeline_mapping")
    return origin + (output_frame - delay) * 1000 / rate
