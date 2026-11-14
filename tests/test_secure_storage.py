import os

import pytest

from services.secure_storage import ensure_private_directory, open_private_file


def test_private_directory_rejects_symlink_root(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"directory symlinks unavailable: {type(error).__name__}")
    with pytest.raises(ValueError, match="symlink"):
        ensure_private_directory(alias)


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits are not Windows ACLs")
def test_sensitive_directory_and_new_file_have_private_modes(tmp_path):
    root = ensure_private_directory(tmp_path / "private")
    path = root / "audio.part"
    with open_private_file(path) as output:
        output.write(b"synthetic")
    assert root.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        open_private_file(path)


def test_private_file_helper_rejects_unintended_modes(tmp_path):
    with pytest.raises(ValueError, match="mode"):
        open_private_file(tmp_path / "unsafe", "r+b")
