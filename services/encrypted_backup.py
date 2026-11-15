"""Authenticated streaming backup envelopes; infrastructure key custody remains external."""

import argparse
import os
from pathlib import Path
import struct
import tempfile
from uuid import uuid4
import zipfile

from services.api.ingest import file_sha256
from services.maintenance import backup, restore, checked

MAGIC = b"MTAI-AESGCM1\0"
CONTEXT = b"med-transcript synthetic backup envelope v2"
DEFAULT_BUDGET = 2 * 1024**3
CHUNK_BYTES = 1024 * 1024
NONCE_BYTES = 12
TAG_BYTES = 16


def _read_exact(stream, size):
    value = stream.read(size)
    if len(value) != size:
        raise ValueError("Truncated encrypted envelope")
    return value


def crypt_file(source, destination, key, *, decrypt=False, max_bytes=DEFAULT_BUDGET):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(key) not in (16, 24, 32) or not 1 <= max_bytes <= 1024**4:
        raise ValueError("Invalid key or size budget")
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError("Refusing to replace existing output")
    temporary = destination.with_name(destination.name + "." + str(uuid4()) + ".part")
    cipher = AESGCM(key)
    processed = 0
    chunks = 0
    try:
        with source.open("rb") as incoming, temporary.open("xb") as output:
            os.chmod(temporary, 0o600)
            if decrypt:
                if _read_exact(incoming, len(MAGIC)) != MAGIC:
                    raise ValueError("Unsupported encrypted envelope")
                while True:
                    header = _read_exact(incoming, 4)
                    length = struct.unpack(">I", header)[0]
                    if length == 0:
                        nonce = _read_exact(incoming, NONCE_BYTES)
                        footer = _read_exact(incoming, TAG_BYTES)
                        cipher.decrypt(
                            nonce,
                            footer,
                            CONTEXT
                            + b"footer\0"
                            + struct.pack(">QQ", processed, chunks),
                        )
                        if incoming.read(1):
                            raise ValueError("Trailing data after encrypted envelope")
                        break
                    if length > CHUNK_BYTES or processed + length > max_bytes:
                        raise ValueError("Encrypted backup size budget exceeded")
                    nonce = _read_exact(incoming, NONCE_BYTES)
                    ciphertext = _read_exact(incoming, length + TAG_BYTES)
                    plaintext = cipher.decrypt(
                        nonce,
                        ciphertext,
                        CONTEXT + b"chunk\0" + struct.pack(">QI", chunks, length),
                    )
                    if len(plaintext) != length:
                        raise ValueError("Encrypted chunk length mismatch")
                    output.write(plaintext)
                    processed += length
                    chunks += 1
            else:
                output.write(MAGIC)
            if not decrypt:
                while data := incoming.read(CHUNK_BYTES):
                    processed += len(data)
                    if processed > max_bytes:
                        raise ValueError("Backup size budget exceeded")
                    nonce = os.urandom(NONCE_BYTES)
                    output.write(struct.pack(">I", len(data)))
                    output.write(nonce)
                    output.write(
                        cipher.encrypt(
                            nonce,
                            data,
                            CONTEXT
                            + b"chunk\0"
                            + struct.pack(">QI", chunks, len(data)),
                        )
                    )
                    chunks += 1
                footer_nonce = os.urandom(NONCE_BYTES)
                output.write(b"\0\0\0\0")
                output.write(footer_nonce)
                output.write(
                    cipher.encrypt(
                        footer_nonce,
                        b"",
                        CONTEXT + b"footer\0" + struct.pack(">QQ", processed, chunks),
                    )
                )
            output.flush()
            os.fsync(output.fileno())
        # Publish only after full authentication, and never overwrite a racing output.
        if os.name == "nt":
            # Windows rename fails if the destination already exists and is atomic.
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "encrypted": not decrypt,
        "bytes": destination.stat().st_size,
        "sha256": file_sha256(destination),
    }


def encrypted_backup(db, assets, destination, key, *, max_bytes=DEFAULT_BUDGET):
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError("Refusing to replace existing backup")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Temporary plaintext requires a protected/encrypted staging volume in deployment.
    with tempfile.TemporaryDirectory(
        prefix="mt-backup-", dir=destination.parent
    ) as temporary:
        root = Path(temporary).resolve()
        os.chmod(root, 0o700)
        source = root / "source"
        receipt = backup(db, assets, source)
        archive = root / "snapshot.zip"
        total = 0
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    total += path.stat().st_size
                    if total > max_bytes:
                        raise ValueError("Backup size budget exceeded")
                    output.write(path, path.relative_to(source).as_posix())
        envelope = crypt_file(archive, destination, key, max_bytes=max_bytes + 1024**2)
    return {
        "status": "encrypted_backup_created",
        "algorithm": f"AES-{len(key) * 8}-GCM",
        "files": receipt["files"],
        "ciphertext_sha256": envelope["sha256"],
        "encrypted": True,
        "managed_key_custody_verified": False,
    }


def encrypted_restore(
    source, destination, tombstones_from, key, *, max_bytes=DEFAULT_BUDGET
):
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError("Restore destination must be new")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="mt-restore-", dir=destination.parent
    ) as temporary:
        root = Path(temporary).resolve()
        os.chmod(root, 0o700)
        archive = root / "authenticated.zip"
        crypt_file(source, archive, key, decrypt=True, max_bytes=max_bytes + 1024**2)
        unpacked = root / "snapshot"
        unpacked.mkdir()
        with zipfile.ZipFile(archive) as package:
            entries = package.infolist()
            names = [e.filename.casefold() for e in entries]
            if (
                len(entries) > 100000
                or len(set(names)) != len(names)
                or sum(e.file_size for e in entries) > max_bytes
            ):
                raise ValueError("Archive extraction budget or uniqueness violation")
            for entry in entries:
                if entry.is_dir():
                    continue
                if (
                    "\\" in entry.filename
                    or ":" in entry.filename
                    or entry.filename.startswith("/")
                ):
                    raise ValueError("Unsafe archive path")
                target = checked(unpacked, entry.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(entry) as incoming, target.open("xb") as output:
                    while chunk := incoming.read(1024 * 1024):
                        output.write(chunk)
        receipt = restore(unpacked, destination, tombstones_from)
    return {
        **receipt,
        "envelope_authenticated": True,
        "real_patient_release_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["keygen", "backup", "restore"])
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--db")
    parser.add_argument("--assets")
    parser.add_argument("--source")
    parser.add_argument("--destination")
    parser.add_argument("--tombstones-from")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_BUDGET)
    args = parser.parse_args()
    keypath = Path(args.key_file)
    if args.action == "keygen":
        with keypath.open("xb") as target:
            target.write(os.urandom(32))
        os.chmod(keypath, 0o600)
        result = {
            "status": "key_created",
            "secret_printed": False,
            "custody_requires_operator": True,
        }
    else:
        key = keypath.read_bytes()
        if args.action == "backup":
            if not args.db or not args.assets or not args.destination:
                parser.error("backup requires db, assets and destination")
            result = encrypted_backup(
                args.db, args.assets, args.destination, key, max_bytes=args.max_bytes
            )
        else:
            if not args.source or not args.destination or not args.tombstones_from:
                parser.error("restore requires source, destination and tombstones-from")
            result = encrypted_restore(
                args.source,
                args.destination,
                args.tombstones_from,
                key,
                max_bytes=args.max_bytes,
            )
    import json

    print(json.dumps(result))


if __name__ == "__main__":
    main()
