import hashlib
import json
import random
import wave
from pathlib import Path

import pytest

from services.detailed_benchmark import coverage, evaluate_case, fast_score, summarize
from services.detailed_benchmark import validated_resume
from services.evaluation import score
from services.prepare_detailed import select
from services.audio_provenance import validate_provenance
from services.api.ingest import file_sha256


def test_bitvector_token_scoring_matches_original_normalization_and_edit_counts():
    rng = random.Random(42)
    words = [
        "0.5",
        "5",
        "mg",
        "mcg",
        "no",
        "not",
        "allergy",
        "patient",
        "mother",
        "don't",
        "5-mg",
    ]
    for _ in range(150):
        a = " ".join(rng.choices(words, k=rng.randrange(30)))
        b = " ".join(rng.choices(words, k=rng.randrange(30)))
        assert fast_score(a, b) == score(a, b)
    assert (
        fast_score("no penicillin allergy 0.5 mg", "penicillin allergy 5 mcg")[
            "normalized_edits"
        ]
        == 3
    )


def test_detailed_selection_excludes_reserved_foreground_and_donor():
    rows = [
        {"item_id": "reserved", "donor_id": "safe", "level_db": -10},
        {"item_id": "safe", "donor_id": "reserved", "level_db": -10},
        {"item_id": "other", "donor_id": "safe", "level_db": -5},
        {"item_id": "eligible", "donor_id": "safe", "level_db": -10},
    ]
    assert select(rows, {"reserved"}, 1) == [rows[-1]]
    with pytest.raises(ValueError):
        select(rows, {"reserved"}, 2)


def test_one_failed_window_retains_all_reference_deletions_and_raw_success(tmp_path):
    audio = tmp_path / "source.wav"
    with wave.open(str(audio), "wb") as out:
        out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        out.writeframes(b"\0\0" * 16000 * 31)
    case = {
        "group_id": "full",
        "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "foreground_id": "patient",
        "condition": "clean",
        "reference_turns": [{"reference": "No penicillin allergy."}],
    }
    calls = []

    def predict(path, context):
        calls.append(context)
        if len(calls) == 2:
            raise RuntimeError("Synthetic native failure")
        return {
            "text": "No penicillin allergy.",
            "segments": [
                {"start_ms": 0, "end_ms": 1000, "text": "No penicillin allergy."}
            ],
        }

    checkpoints = []
    row = evaluate_case(
        case,
        audio,
        predict,
        "fixed",
        lambda current: checkpoints.append(len(current["chunks"])),
    )
    assert (
        row["failed"]
        and row["hypothesis"] == ""
        and row["partial_hypothesis_for_diagnostics_only"] == "No penicillin allergy."
    )
    assert row["normalized_edits"] == row["reference_words"] == 3
    assert row["input_coverage_complete"] and checkpoints == [1, 2]
    assert all(validate_provenance(crop["audio_provenance"]) for crop in row["chunks"])
    assert summarize([row])["wer_gate"]["status"] == "fail"
    assert not row["native_timestamp_bounds_valid"]


def test_coverage_rejects_missing_prefix_gap_or_tail():
    assert coverage([(0, 30), (28, 50)], 50)
    assert not coverage([(1, 30), (28, 50)], 50)
    assert not coverage([(0, 30), (31, 50)], 50)
    assert not coverage([(0, 49)], 50)


def test_resume_rejects_altered_references_models_or_scores():
    from copy import deepcopy

    case = {
        "group_id": "one",
        "condition": "clean",
        "audio_sha256": "a" * 64,
        "reference_turns": [{"reference": "No allergy."}],
    }
    row = {
        "id": "one",
        "condition": "clean",
        "input_sha256": "a" * 64,
        "input_coverage_complete": True,
        "failed": False,
        "reference": "No allergy.",
        "hypothesis": "No allergy.",
        **fast_score("No allergy.", "No allergy."),
    }
    prior = {
        "candidate_id": "model",
        "mode": "fixed",
        "runtime": {"revision": "pinned"},
        "cases": [row],
    }
    assert validated_resume(
        prior, {"cases": [case]}, {"revision": "pinned"}, "model", "fixed"
    ) == [row]
    altered = deepcopy(prior)
    altered["cases"][0]["normalized_edits"] = 1
    with pytest.raises(ValueError):
        validated_resume(
            altered, {"cases": [case]}, {"revision": "pinned"}, "model", "fixed"
        )
    with pytest.raises(ValueError):
        validated_resume(
            prior, {"cases": [case]}, {"revision": "changed"}, "model", "fixed"
        )


def test_detailed_suite_v3_binds_source_and_memory_budget():
    suite_path = "evaluation/detailed-suite-v3.json"
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    assert suite["schema_version"] == "detailed_campaign_v2"
    assert suite["maximum_normalized_wer"] == 0.05
    assert suite["resource_budget"]["max_process_resident_bytes"] == 16 * 1024**3
    assert suite["resource_budget"]["models_loaded_simultaneously"] == 1
    for source, digest in suite["source_text_sha256"].items():
        assert file_sha256(source) == digest
    candidate = next(
        item for item in suite["jobs"] if item["candidate_id"] == "faster-whisper-large-v3"
    )
    resume = candidate["resume_by_mode"]["speech_aware"]
    assert file_sha256(resume["path"]) == resume["sha256"]
