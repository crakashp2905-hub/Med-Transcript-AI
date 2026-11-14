import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4

import pytest

from services.api.storage import Store
from services.maintenance import backup, restore, purge, reconcile
from tests.test_foundation import headers, queue_upload
from tests.test_review_workflow import prepare


def test_backup_restore_and_post_backup_tombstone(setup, tmp_path):
    client, path, _ = setup
    eid, tx, _ = prepare(client, path)
    assets = str(Path(path).parent / "assets")
    snapshot = str(tmp_path / "snapshot")
    assert backup(path, assets, snapshot)["status"] == "backed_up"
    assert (
        client.post(
            f"/v1/encounters/{eid}/deletion-requests", headers=headers()
        ).status_code
        == 202
    )
    target = str(tmp_path / "restored")
    assert restore(snapshot, target, path)["tombstones_applied"] == 1
    with Store(str(Path(target) / "database.sqlite3")).transaction() as con:
        assert con.execute(
            "SELECT deleted_at FROM encounters WHERE id=?", (eid,)
        ).fetchone()[0]
    assert not list((Path(target) / "assets").glob("*.wav"))
    assert (
        purge(path, assets)["requests"][0]["status"] == "primary_purged_backups_pending"
    )
    with Store(path).transaction() as con:
        assert (
            con.execute("SELECT body FROM encounters WHERE id=?", (eid,)).fetchone()[0]
            == "{}"
        )
        assert (
            con.execute("SELECT COUNT(*) FROM transcript_versions").fetchone()[0] == 0
        )


def test_restore_rejects_modified_backup(setup, tmp_path):
    _, path, _ = setup
    source = tmp_path / "backup"
    backup(path, str(tmp_path / "assets"), str(source))
    (source / "database.sqlite3").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        restore(str(source), str(tmp_path / "restore"), path)


def test_local_restore_recovery_target_and_snapshot_rpo(tmp_path, capsys):
    path = str(tmp_path / "source.sqlite3")
    assets = tmp_path / "source-assets"
    assets.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    baseline = [str(uuid4()) for _ in range(10)]
    with Store(path).transaction() as con:
        con.executemany(
            "INSERT INTO encounters(id,tenant,clinician,body,created_at) VALUES(?,?,?,?,?)",
            [(eid, "tenant", "clinician", "{}", now) for eid in baseline],
        )

    snapshot = tmp_path / "snapshot"
    assert backup(path, str(assets), str(snapshot))["status"] == "backed_up"
    post_snapshot = str(uuid4())
    with Store(path).transaction() as con:
        con.execute(
            "INSERT INTO encounters(id,tenant,clinician,body,created_at) VALUES(?,?,?,?,?)",
            (post_snapshot, "tenant", "clinician", "{}", now),
        )

    target = tmp_path / "restored"
    started = time.perf_counter()
    result = restore(str(snapshot), str(target), path)
    elapsed = time.perf_counter() - started
    with Store(str(target / "database.sqlite3")).transaction() as con:
        restored = {
            row[0] for row in con.execute("SELECT id FROM encounters")
        }

    assert result["status"] == "restored_for_operator_review"
    assert set(baseline) <= restored
    assert post_snapshot not in restored
    assert elapsed < 60
    print(
        json.dumps(
            {
                "restore_rto_seconds": round(elapsed, 6),
                "local_engineering_rto_target_seconds": 60,
                "baseline_records_recovered": len(baseline),
                "post_snapshot_records_recovered": int(post_snapshot in restored),
                "snapshot_rpo_semantics": "all acknowledged records inside the last verified snapshot recovered",
            },
            sort_keys=True,
        )
    )


def test_reconcile_is_dry_run_and_does_not_delete_unrelated_files(setup, tmp_path):
    _, path, _ = setup
    assets = tmp_path / "assets"
    assets.mkdir(exist_ok=True)
    orphan = assets / f"{uuid4()}.wav"
    orphan.write_bytes(b"orphan")
    unrelated = assets / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    assert reconcile(path, str(assets))["candidates"] == [orphan.name]
    assert orphan.exists()
    reconcile(path, str(assets), apply=True)
    assert not orphan.exists() and unrelated.exists()


def test_reconcile_protects_live_normalization_and_reclaims_abandoned_temp(setup):
    client, path, _ = setup
    _, upload, _, _ = queue_upload(client)
    assets = Path(path).parent / "assets"
    source = assets / f"{upload['id']}.wav"
    temporary = assets / f"{upload['id']}.{uuid4()}.normalized.wav"
    temporary.write_bytes(b"staged normalized audio")
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    with Store(path).transaction() as con:
        job_id = con.execute(
            "SELECT id FROM jobs WHERE upload=? AND stage='audio_ingest'",
            (upload["id"],),
        ).fetchone()[0]
        con.execute(
            "UPDATE jobs SET status='running', lease_token=?, lease_expires_at=? WHERE id=?",
            (str(uuid4()), expires, job_id),
        )

    assert reconcile(path, str(assets), apply=True)["candidates"] == []
    assert temporary.exists() and source.exists()
    with Store(path).transaction() as con:
        con.execute(
            "UPDATE jobs SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE id=?",
            (job_id,),
        )
    report = reconcile(path, str(assets), apply=True)
    assert temporary.name in report["candidates"]
    assert not temporary.exists()
    assert source.exists()
