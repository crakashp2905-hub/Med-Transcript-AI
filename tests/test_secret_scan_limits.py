import subprocess

from services.secret_scan import MAX_TEXT_BYTES, scan


def test_oversized_text_is_reported_and_prevents_clean_pass(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    large = tmp_path / "large-source.txt"
    large.write_bytes(b"x" * (MAX_TEXT_BYTES + 1))
    report = scan(tmp_path)

    assert report["status"] == "incomplete"
    assert report["skipped_files"] == [
        {
            "path": "large-source.txt",
            "size_bytes": MAX_TEXT_BYTES + 1,
            "reason": "size_limit",
        }
    ]


def test_oversized_file_does_not_hide_findings_in_small_files(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "large.txt").write_bytes(b"x" * (MAX_TEXT_BYTES + 1))
    (tmp_path / "small.env").write_text(
        'api_key="' + ("secret-value-" * 3) + '"', encoding="utf-8"
    )
    report = scan(tmp_path)

    assert report["status"] == "fail"
    assert report["findings"]
    assert report["skipped_files"][0]["path"] == "large.txt"
