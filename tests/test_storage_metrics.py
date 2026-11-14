from services.storage_metrics import compare_encounter_storage, snapshot_storage


def test_encounter_storage_growth_retention_and_deletion_footprint(tmp_path):
    encounter = tmp_path / "encounter-1"
    encounter.mkdir()
    before = snapshot_storage(encounter)
    note = encounter / "note.json"
    audio = encounter / "source.wav"
    note.write_bytes(b"note-data")
    audio.write_bytes(b"audio-bytes-123")
    after_capture = snapshot_storage(encounter)
    growth = compare_encounter_storage("encounter-1", before, after_capture)
    assert growth["added_or_grown_bytes"] == len(b"note-data") + len(b"audio-bytes-123")
    assert growth["retained_audio_bytes_after"] == len(b"audio-bytes-123")

    audio.unlink()
    after_delete = snapshot_storage(encounter)
    deletion = compare_encounter_storage("encounter-1", after_capture, after_delete)
    assert deletion["deleted_file_count"] == 1
    assert deletion["deleted_file_bytes"] == len(b"audio-bytes-123")
    assert deletion["retained_audio_bytes_after"] == 0
    assert deletion["deleted_paths"] == ["source.wav"]
