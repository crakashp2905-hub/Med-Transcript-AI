import hashlib
import json
import wave

import numpy as np
import pytest
from services.offline_acceptance import pytest_basetemp

from services.asr.training_augmentation import (
    RECIPES,
    _seed,
    apply_augmentation,
    generate_augmentations,
)
from services.audio_provenance import file_sha256


def _source_wav(path, frames=16000):
    x = np.arange(frames, dtype=np.float64)
    signal = (0.2 * np.sin(2 * np.pi * 220 * x / 16000) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(signal.tobytes())
    return signal


def test_augmentation_operations_are_seeded_label_independent_and_bounded():
    source = np.full(2048, 1200, dtype="<i2")
    seed = _seed("sample-1", "synthetic-pink-noise-20db")
    noisy_a, params, safety = apply_augmentation(
        source, "synthetic-pink-noise-20db", seed
    )
    noisy_b, _, _ = apply_augmentation(source, "synthetic-pink-noise-20db", seed)
    other_seed, _, _ = apply_augmentation(source, "synthetic-pink-noise-20db", seed + 1)
    assert np.array_equal(noisy_a, noisy_b)
    assert not np.array_equal(noisy_a, other_seed)
    assert params["snr_db"] == 20.0
    assert 0 < safety <= 1
    assert np.max(np.abs(noisy_a.astype(np.int32))) <= 32767

    stretched, stretch_params, _ = apply_augmentation(
        source, "speed-perturb-104pct", _seed("sample-1", "speed-perturb-104pct")
    )
    assert stretched.size == stretch_params["output_frames"]
    assert 0.95 < stretched.size / source.size < 0.97
    assert stretch_params["playback_speed_factor"] == 1.04
    gained, gain_params, _ = apply_augmentation(
        source, "gain-minus3db", _seed("sample-1", "gain-minus3db")
    )
    assert gained.size == source.size
    assert gain_params["gain_db"] == -3.0
    assert set(RECIPES) == {
        "gain-minus3db",
        "speed-perturb-104pct",
        "synthetic-pink-noise-20db",
    }


def test_augmentation_generation_binds_parent_hashes_and_inherits_split():
    tmp_path = pytest_basetemp("asr-augment")
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source.wav"
    _source_wav(source)
    source_sha = file_sha256(source)
    ref_sha = hashlib.sha256(b"reference label").hexdigest()
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "schema_version": "asr_original_consultation_group_split_v1",
                "complete": True,
                "acceptance_labels_accessed": False,
                "group_assignments": {"reserved_acceptance": ["day5_consultation05"]},
                "rows": [
                    {
                        "sample_id": "sample-1",
                        "consultation_group_id": "consultation_train",
                        "contributing_group_ids": ["consultation_train"],
                        "split": "training",
                        "source_dataset": "primock57-expanded-v1",
                        "source_audio_path": str(source),
                        "audio_sha256": source_sha,
                        "reference_sha256": ref_sha,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "augmentations-v1"
    report = generate_augmentations(split_path, output)
    assert report["parent_training_samples"] == 1
    assert report["augmentation_count"] == 3
    assert report["augmentation_count_by_transform"] == {name: 1 for name in RECIPES}
    assert report["reserved_acceptance_groups_used"] == []
    assert all(row["split"] == "training" for row in report["augmentation_rows"])
    assert all(
        row["parent_audio_sha256"] == source_sha for row in report["augmentation_rows"]
    )
    assert all(
        row["reference_sha256"] == ref_sha for row in report["augmentation_rows"]
    )
    assert all(
        row["split_inherited_from_parent_group"] for row in report["augmentation_rows"]
    )
    for row in report["augmentation_rows"]:
        target = output / row["augmented_audio_path"]
        assert file_sha256(target) == row["augmented_audio_sha256"]
    with pytest.raises(ValueError, match="augmentation_output_version_already_exists"):
        generate_augmentations(split_path, output)
