import subprocess

import pytest

from scripts.repro_clean import materialize_commit


def test_clean_snapshot_copies_only_committed_regular_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        cwd=repo,
        check=True,
    )
    tracked = repo / "tracked.txt"
    tracked.write_text("committed", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=repo,
        check=True,
    )
    (repo / "untracked.txt").write_text("developer data", encoding="utf-8")
    snapshot = tmp_path / "outside" / "snapshot"
    materialize_commit(repo, snapshot)
    assert (snapshot / "tracked.txt").read_text(encoding="utf-8") == "committed"
    assert not (snapshot / "untracked.txt").exists()
    assert tracked.read_text(encoding="utf-8") == "committed"
    assert (repo / "untracked.txt").read_text(encoding="utf-8") == "developer data"


def test_clean_snapshot_refuses_repository_destinations(tmp_path):
    with pytest.raises(ValueError, match="inside_repository"):
        materialize_commit(tmp_path, tmp_path / "snapshot")
