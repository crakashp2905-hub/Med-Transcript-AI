"""Local synthetic-data maintenance. Backups are plaintext and require protected storage."""

import argparse
import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from services.api.ingest import file_sha256
from services.api.storage import Store


def now():
    return datetime.now(timezone.utc).isoformat()


def checked(root, relative):
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve():
        raise ValueError("Backup path escapes its root")
    return target


def backup(db, assets, destination):
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=False)
    try:
        with Store(db).transaction() as con:
            with sqlite3.connect(db) as source, sqlite3.connect(target / "database.sqlite3") as output:
                source.backup(output)
            (target / "assets").mkdir()
            for row in con.execute("SELECT id,status FROM uploads"):
                if row["status"] not in ("uploaded", "complete"):
                    continue
                for suffix in (".wav", ".normalized.wav"):
                    source = Path(assets) / f"{row['id']}{suffix}"
                    if source.is_file():
                        shutil.copyfile(source, target / "assets" / source.name)
        manifest = {"schema_version": "1.0", "created_at": now(), "encrypted": False,
            "files": {str(path.relative_to(target)).replace("\\", "/"): file_sha256(path)
                      for path in target.rglob("*") if path.is_file()}}
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {"status": "backed_up", "files": len(manifest["files"]), "encrypted": False}
    except BaseException:
        # Keep incomplete backups identifiable rather than advertising a successful receipt.
        (target / "INCOMPLETE").write_text("Backup did not finish.", encoding="utf-8")
        raise


def restore(source, destination, tombstones_from):
    root, target = Path(source).resolve(), Path(destination).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (root / "INCOMPLETE").exists():
        raise ValueError("Incomplete backup")
    for relative, digest in manifest["files"].items():
        if file_sha256(checked(root, relative)) != digest:
            raise ValueError("Backup integrity failure")
    if "database.sqlite3" not in manifest["files"]:
        raise ValueError("Backup database is missing")
    with Store(tombstones_from).transaction() as con:
        deleted = {row["id"]: row["deleted_at"] for row in con.execute("SELECT id,deleted_at FROM encounters WHERE deleted_at IS NOT NULL")}
    target.mkdir(parents=True, exist_ok=False)
    for relative in manifest["files"]:
        output = checked(target, relative)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checked(root, relative), output)
    db = str(target / "database.sqlite3")
    with Store(db).transaction() as con:
        for eid, deleted_at in deleted.items():
            con.execute("UPDATE encounters SET deleted_at=? WHERE id=?", (deleted_at, eid))
            con.execute("UPDATE jobs SET status='cancelled',lease_token=NULL,lease_expires_at=NULL WHERE encounter=? AND status IN ('queued','running')", (eid,))
            for row in con.execute("SELECT id FROM uploads WHERE encounter=?", (eid,)):
                for suffix in (".wav", ".normalized.wav"):
                    (target / "assets" / f"{row['id']}{suffix}").unlink(missing_ok=True)
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Restored database failed integrity check")
    return {"status": "restored_for_operator_review", "tombstones_applied": len(deleted)}


def purge(db, assets):
    results = []
    with Store(db).transaction() as con:
        if not db.startswith(("postgresql://", "postgres://")):
            con.execute("PRAGMA secure_delete=ON")
        requests = con.execute("SELECT * FROM deletion_requests WHERE status='pending'").fetchall()
        for request in requests:
            eid = request["encounter"]
            row = con.execute("SELECT * FROM encounters WHERE id=?", (eid,)).fetchone()
            if row["legal_hold"] or con.execute("SELECT 1 FROM approvals WHERE encounter=?", (eid,)).fetchone():
                results.append({"id": request["id"], "status": "held_for_retention_review"})
                continue
            try:
                for upload in con.execute("SELECT id FROM uploads WHERE encounter=?", (eid,)):
                    for suffix in (".wav", ".normalized.wav"):
                        checked(Path(assets), f"{upload['id']}{suffix}").unlink(missing_ok=True)
            except OSError:
                results.append({"id": request["id"], "status": "asset_deletion_pending"})
                continue
            for table in ("review_metrics", "model_proposals", "exports", "approvals", "documents", "transcript_versions", "jobs", "uploads", "authorizations"):
                con.execute(f"DELETE FROM {table} WHERE encounter=?", (eid,))
            con.execute("DELETE FROM idempotency WHERE operation LIKE ? OR response LIKE ?", (f"%{eid}%", f"%{eid}%"))
            con.execute("UPDATE encounters SET body='{}',current_note=NULL,current_transcript=NULL WHERE id=?", (eid,))
            con.execute("UPDATE deletion_requests SET status='primary_purged_backups_pending' WHERE id=?", (request["id"],))
            results.append({"id": request["id"], "status": "primary_purged_backups_pending"})
    return {"requests": results, "backup_expiry": "requires_operator_confirmation"}


def reconcile(db, assets, apply=False):
    root = Path(assets).resolve()
    candidates = []
    with Store(db).transaction() as con:
        uploads = {row["id"]: row for row in con.execute("SELECT uploads.*,encounters.legal_hold FROM uploads JOIN encounters ON encounters.id=uploads.encounter")}
        for path in root.glob("*"):
            match = re.fullmatch(r"([a-f0-9-]{36})(?:\.[a-f0-9-]{36}(?:\.part|\.normalized\.wav)|(?:\.normalized)?\.wav)", path.name)
            if not match or not path.is_file() or path.is_symlink():
                continue
            row = uploads.get(match[1])
            safe = row is None or (not row["legal_hold"] and row["status"] != "complete" and row["expires_at"] <= now())
            if row is not None and not row["legal_hold"] and path.name.endswith(".normalized.wav") and len(path.name) > 52:
                live = con.execute("SELECT 1 FROM jobs WHERE upload=? AND stage='audio_ingest' AND status='running' AND lease_expires_at>?", (row["id"], now())).fetchone()
                safe = not live
            if safe:
                candidates.append(path.name)
                if apply:
                    checked(root, path.name).unlink()
    return {"applied": apply, "candidates": candidates}


def main():
    parser = argparse.ArgumentParser(description="Synthetic development maintenance; protect plaintext backups")
    parser.add_argument("action", choices=["backup", "restore", "purge", "reconcile", "integrity"])
    parser.add_argument("--db", default="data/development.sqlite3")
    parser.add_argument("--assets", default="data/assets")
    parser.add_argument("--destination")
    parser.add_argument("--source")
    parser.add_argument("--tombstones-from")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.db.startswith(("postgres://", "postgresql://")):
        raise SystemExit("Use PostgreSQL-native backup/restore and the deployment runbook.")
    if args.action == "backup":
        if not args.destination: parser.error("backup requires --destination")
        result = backup(args.db, args.assets, args.destination)
    elif args.action == "restore":
        if not args.source or not args.destination or not args.tombstones_from:
            parser.error("restore requires --source, --destination and --tombstones-from")
        result = restore(args.source, args.destination, args.tombstones_from)
    elif args.action == "purge": result = purge(args.db, args.assets)
    elif args.action == "reconcile": result = reconcile(args.db, args.assets, args.apply)
    else:
        with Store(args.db).transaction() as con:
            result = {"integrity": con.execute("PRAGMA integrity_check").fetchone()[0], "foreign_key_violations": len(con.execute("PRAGMA foreign_key_check").fetchall())}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
