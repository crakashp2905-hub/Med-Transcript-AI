import json
from pathlib import Path
from uuid import uuid4

import pytest

from services.api.storage import Store
from services.maintenance import backup, restore, purge, reconcile
from tests.test_foundation import setup, headers
from tests.test_review_workflow import prepare


def test_backup_restore_and_post_backup_tombstone(setup, tmp_path):
    client, path, _ = setup
    eid, tx, _ = prepare(client, path)
    assets = str(Path(path).parent / "assets")
    snapshot = str(tmp_path / "snapshot")
    assert backup(path, assets, snapshot)["status"] == "backed_up"
    assert client.post(f"/v1/encounters/{eid}/deletion-requests", headers=headers()).status_code == 202
    target = str(tmp_path / "restored")
    assert restore(snapshot, target, path)["tombstones_applied"] == 1
    with Store(str(Path(target)/"database.sqlite3")).transaction() as con:
        assert con.execute("SELECT deleted_at FROM encounters WHERE id=?", (eid,)).fetchone()[0]
    assert not list((Path(target)/"assets").glob("*.wav"))
    assert purge(path, assets)["requests"][0]["status"] == "primary_purged_backups_pending"
    with Store(path).transaction() as con:
        assert con.execute("SELECT body FROM encounters WHERE id=?", (eid,)).fetchone()[0] == "{}"
        assert con.execute("SELECT COUNT(*) FROM transcript_versions").fetchone()[0] == 0


def test_restore_rejects_modified_backup(setup, tmp_path):
    _, path, _ = setup
    source = tmp_path / "backup"
    backup(path, str(tmp_path / "assets"), str(source))
    (source / "database.sqlite3").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        restore(str(source), str(tmp_path / "restore"), path)


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
