"""Best-effort private local storage primitives for sensitive artifacts.

POSIX modes are enforced here. Windows ACL provisioning remains a deployment
responsibility and is intentionally reported as an unresolved platform check.
"""

import os
from pathlib import Path


def ensure_private_directory(path: str | Path) -> Path:
    """Create a private directory and reject a symlink at the configured root."""
    root = Path(path)
    if root.is_symlink():
        raise ValueError("sensitive_storage_root_symlink_forbidden")
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("sensitive_storage_root_invalid")
    if os.name == "posix":
        root.chmod(0o700)
        if root.stat().st_mode & 0o077:
            raise PermissionError("sensitive_storage_directory_not_private")
    return root


def open_private_file(path: str | Path, mode: str = "xb"):
    """Create a new binary sensitive artifact with restrictive POSIX permissions."""
    if mode not in {"xb", "x+b", "wb", "w+b"}:
        raise ValueError("sensitive_storage_creation_mode_invalid")
    target = Path(path)
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    try:
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
        return os.fdopen(descriptor, "w+b" if "+" in mode else "wb")
    except BaseException:
        os.close(descriptor)
        target.unlink(missing_ok=True)
        raise
