import pytest

from services.maintenance import checked


def test_checked_rejects_traversal_and_absolute_paths(tmp_path):
    root = tmp_path / "assets"
    root.mkdir()

    for path in ("../outside", "nested/../../outside", str(tmp_path / "outside")):
        with pytest.raises(ValueError):
            checked(root, path)


def test_checked_rejects_symlink_components_and_symlink_roots(tmp_path):
    root = tmp_path / "assets"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "redirect"
    root_alias = tmp_path / "assets-alias"
    try:
        link.symlink_to(outside, target_is_directory=True)
        root_alias.symlink_to(root, target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(
            f"directory symlinks unavailable on this host: {type(error).__name__}"
        )

    with pytest.raises(ValueError, match="symlink"):
        checked(root, "redirect/file.wav")
    with pytest.raises(ValueError, match="symlink"):
        checked(root_alias, "file.wav")
