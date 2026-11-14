import errno
import asyncio
import hashlib
import io
import sqlite3
import threading
import wave

import httpx

from tests.test_foundation import (
    create,
    headers,
    authorization,
    upload_session,
    wav_bytes,
)
from tests.test_recovery import append


def test_disk_full_during_chunk_fsync_keeps_offset_uncommitted_and_retries(
    setup, monkeypatch
):
    client, db, _ = setup
    eid = create(client)
    content = wav_bytes()
    upload, _ = upload_session(client, eid, content)
    chunk = content[:100]

    def disk_full(_descriptor):
        raise OSError(errno.ENOSPC, "synthetic full disk")

    monkeypatch.setattr("services.api.resumable.os.fsync", disk_full)
    failed = append(client, upload["content_url"], chunk, 0)
    assert failed.status_code == 503
    assert failed.json()["code"] == "asset_storage_unavailable"
    state = client.get(
        f"/v1/encounters/{eid}/audio-uploads/{upload['id']}", headers=headers()
    ).json()
    assert state["status"] == "open" and state["received_bytes"] == 0

    monkeypatch.undo()
    retried = append(client, upload["content_url"], chunk, 0)
    assert retried.status_code == 200
    assert retried.json()["received_bytes"] == len(chunk)


def test_database_lock_during_chunk_commit_returns_retryable_storage_error(
    setup, monkeypatch
):
    client, db, _ = setup
    eid = create(client)
    content = wav_bytes()
    upload, _ = upload_session(client, eid, content)
    blocker = sqlite3.connect(db)
    blocker.execute("BEGIN IMMEDIATE")
    original_connect = sqlite3.connect

    def short_timeout_connect(*args, **kwargs):
        kwargs["timeout"] = 0.01
        return original_connect(*args, **kwargs)

    monkeypatch.setattr("services.api.storage.sqlite3.connect", short_timeout_connect)
    try:
        response = append(client, upload["content_url"], content[:100], 0)
    finally:
        blocker.rollback()
        blocker.close()
    assert response.status_code == 503
    assert response.json()["code"] == "storage_unavailable"


def test_slow_storage_does_not_advance_upload_offset_before_fsync(setup, monkeypatch):
    client, db, _ = setup
    eid = create(client)
    content = wav_bytes()
    upload, _ = upload_session(client, eid, content)
    chunk = content[:100]
    entered_fsync, release_fsync = threading.Event(), threading.Event()
    original_fsync = __import__("os").fsync
    result = []

    def delayed_fsync(descriptor):
        entered_fsync.set()
        if not release_fsync.wait(5):
            raise TimeoutError("synthetic slow storage gate timed out")
        return original_fsync(descriptor)

    monkeypatch.setattr("services.api.resumable.os.fsync", delayed_fsync)
    request = threading.Thread(
        target=lambda: result.append(append(client, upload["content_url"], chunk, 0)),
        daemon=True,
    )
    request.start()
    assert entered_fsync.wait(2)
    with sqlite3.connect(db) as observer:
        received = observer.execute(
            "SELECT received_bytes FROM uploads WHERE id=?", (upload["id"],)
        ).fetchone()[0]
    assert received == 0
    release_fsync.set()
    request.join(timeout=5)
    assert not request.is_alive()
    assert result[0].status_code == 200
    assert result[0].json()["received_bytes"] == len(chunk)


def test_client_disconnect_during_chunk_body_leaves_upload_uncommitted(setup):
    client, db, _ = setup
    eid = create(client)
    content = wav_bytes()
    upload, _ = upload_session(client, eid, content)
    chunk = content[:100]
    request_headers = {
        **headers(),
        "Content-Type": "audio/wav",
        "Upload-Offset": "0",
        "Upload-Chunk-SHA256": hashlib.sha256(chunk).hexdigest(),
    }

    async def disconnecting_body():
        yield chunk[:40]
        raise httpx.ReadError("synthetic client disconnect")

    async def send_request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client.app),
            base_url="http://testserver",
        ) as local_client:
            try:
                await local_client.patch(
                    upload["content_url"],
                    content=disconnecting_body(),
                    headers=request_headers,
                )
            except httpx.ReadError:
                pass

    asyncio.run(send_request())
    from services.api.storage import Store

    with Store(db).transaction() as con:
        state = con.execute(
            "SELECT status,received_bytes FROM uploads WHERE id=?", (upload["id"],)
        ).fetchone()
    assert state["status"] == "open" and state["received_bytes"] == 0


def stream(client, eid):
    route = f"/v1/encounters/{eid}"
    client.post(route + "/authorizations", headers=headers(), json=authorization())
    response = client.post(
        route + "/stream-uploads",
        headers=headers(),
        json={"format": "pcm", "channels": 1, "media_type": "audio/wav"},
    )
    assert response.status_code == 201, response.text
    return route, response.json()


def test_live_prefix_requires_sealing_and_recovers_valid_wav(setup):
    client, _, _ = setup
    eid = create(client)
    route, item = stream(client, eid)
    raw = wav_bytes()[44:]
    assert (
        append(client, item["content_url"], raw, 44).json()["received_bytes"]
        == len(raw) + 44
    )
    assert (
        client.post(
            route + f"/audio-uploads/{item['id']}/complete", headers=headers()
        ).status_code
        == 409
    )
    workspace = client.get(route + "/workspace", headers=headers()).json()
    assert workspace["transcript"] is None
    assert workspace["note"] is None and workspace["approval"] is None
    recovery = client.get(
        route + f"/stream-uploads/{item['id']}/recovery", headers=headers()
    )
    assert recovery.status_code == 200
    with wave.open(io.BytesIO(recovery.content)) as audio:
        assert audio.getnframes() == len(raw) // 2
        assert audio.readframes(audio.getnframes()) == raw
    body = {
        "bytes": len(recovery.content),
        "sha256": hashlib.sha256(recovery.content).hexdigest(),
    }
    sealed = client.post(
        route + f"/stream-uploads/{item['id']}/seal", headers=headers(), json=body
    )
    assert sealed.status_code == 200, sealed.text
    assert (
        client.post(
            route + f"/stream-uploads/{item['id']}/seal", headers=headers(), json=body
        ).status_code
        == 200
    )
    assert (
        client.post(
            route + f"/audio-uploads/{item['id']}/complete", headers=headers()
        ).status_code
        == 202
    )
    assert (
        client.get(route + "/workspace", headers=headers()).json()["transcript"] is None
    )


def test_live_seal_integrity_scope_and_withdrawal_fail_closed(setup):
    client, _, _ = setup
    eid = create(client)
    route, item = stream(client, eid)
    raw = wav_bytes()[44:]
    append(client, item["content_url"], raw, 44)
    url = route + f"/stream-uploads/{item['id']}/seal"
    body = {"bytes": len(raw) + 44, "sha256": "0" * 64}
    assert client.post(url, headers=headers("b" * 40), json=body).status_code == 404
    assert client.post(url, headers=headers(), json=body).status_code == 422
    assert (
        client.get(route + f"/audio-uploads/{item['id']}", headers=headers()).json()[
            "status"
        ]
        == "open"
    )
    from services.api.storage import Store

    with Store(setup[1]).transaction() as con:
        con.execute(
            "UPDATE authorizations SET withdrawn_at='2026-01-01T00:00:00+00:00'"
        )
    assert client.post(url, headers=headers(), json=body).status_code == 403
    assert append(client, item["content_url"], raw, len(raw) + 44).status_code == 403


def test_backup_includes_only_committed_live_prefix_and_seal_recovers_rename(
    setup, tmp_path
):
    from pathlib import Path
    from services.maintenance import backup, restore

    client, db, _ = setup
    eid = create(client)
    route, item = stream(client, eid)
    raw = wav_bytes()[44:]
    append(client, item["content_url"], raw, 44)
    partial = Path(db).parent / "assets" / f"{item['id']}.resume.part"
    with partial.open("ab") as output:
        output.write(b"uncommitted")
    snapshot = tmp_path / "snapshot"
    backup(db, partial.parent, snapshot)
    saved = snapshot / "assets" / partial.name
    assert saved.stat().st_size == 44 + len(raw)
    restored = tmp_path / "restored"
    restore(snapshot, restored, db)
    assert (restored / "assets" / partial.name).read_bytes() == saved.read_bytes()
    # Crash between the source rename and SQL commit: retry must seal the
    # original prefix without permitting an altered source.
    recovery = client.get(
        route + f"/stream-uploads/{item['id']}/recovery", headers=headers()
    ).content
    destination = partial.with_name(f"{item['id']}.wav")
    destination.write_bytes(recovery)
    partial.unlink()
    body = {"bytes": len(recovery), "sha256": hashlib.sha256(recovery).hexdigest()}
    assert (
        client.post(
            route + f"/stream-uploads/{item['id']}/seal", headers=headers(), json=body
        ).status_code
        == 200
    )
