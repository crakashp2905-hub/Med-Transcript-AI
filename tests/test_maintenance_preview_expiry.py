from pathlib import Path

from services.api.storage import Store
from services.maintenance import expire_previews


def _expired_preview(tmp_path, *, saved_source):
    db = tmp_path / "store.sqlite3"
    assets = tmp_path / "assets"
    assets.mkdir()
    store = Store(str(db))
    upload_id = "upload-1"
    job_id = "job-1"
    with store.transaction() as con:
        con.execute(
            "INSERT INTO encounters(id,tenant,clinician,body,created_at) VALUES(?,?,?,?,?)",
            ("encounter-1", "tenant-1", "clinician-1", "{}", "2020-01-01"),
        )
        con.execute(
            "INSERT INTO uploads(id,encounter,expected_bytes,expected_sha256,status,created_at,expires_at) VALUES(?,?,?,?,?,?,?)",
            (
                upload_id,
                "encounter-1",
                1,
                "0" * 64,
                "complete",
                "2020-01-01",
                "2030-01-01",
            ),
        )
        con.execute(
            "INSERT INTO jobs(id,upload,encounter,status,created_at,updated_at,preview_only) VALUES(?,?,?,?,?,?,1)",
            (job_id, upload_id, "encounter-1", "succeeded", "2020-01-01", "2020-01-01"),
        )
        if saved_source:
            con.execute(
                "INSERT INTO transcript_versions(id,encounter,upload,job,version,sha256,body,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    "transcript-1",
                    "encounter-1",
                    upload_id,
                    job_id,
                    1,
                    "1" * 64,
                    "{}",
                    "2020-01-01",
                ),
            )
    for suffix in (".wav", ".normalized.wav", ".resume.part"):
        (assets / f"{upload_id}{suffix}").write_bytes(b"audio")
    return db, assets, upload_id, job_id


def test_expiring_preview_preserves_saved_source_audio(tmp_path):
    db, assets, upload_id, job_id = _expired_preview(tmp_path, saved_source=True)

    assert expire_previews(str(db), str(assets))["expired_preview_caches"] == 1

    assert (Path(assets) / f"{upload_id}.wav").exists()
    assert not (Path(assets) / f"{upload_id}.normalized.wav").exists()
    assert not (Path(assets) / f"{upload_id}.resume.part").exists()
    with Store(str(db)).transaction() as con:
        row = con.execute(
            "SELECT preview_cache_expired,result FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
    assert row["preview_cache_expired"] == 1
    assert '"approvable": false' in row["result"]


def test_expiring_unreferenced_preview_removes_source_audio(tmp_path):
    db, assets, upload_id, _ = _expired_preview(tmp_path, saved_source=False)

    assert expire_previews(str(db), str(assets))["expired_preview_caches"] == 1

    assert not (Path(assets) / f"{upload_id}.wav").exists()
