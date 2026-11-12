from services.source_change_detector import canonical_sha256, compare_acceptance


def test_acceptance_remains_valid_when_source_and_toolchain_match():
    source = {"services/app.py": "a" * 64}
    tools = {"python": "3.13", "packages": [["pytest", "9.0"]]}
    report = {
        "source_sha256": source,
        "toolchain": tools,
        "toolchain_sha256": canonical_sha256(tools),
    }
    result = compare_acceptance(report, source_files=source, toolchain=tools)
    assert result["status"] == "valid"
    assert result["invalidated"] is False


def test_source_change_invalidates_an_acceptance_report():
    tools = {"python": "3.13"}
    report = {
        "source_sha256": {"services/app.py": "a" * 64},
        "toolchain": tools,
        "toolchain_sha256": canonical_sha256(tools),
    }
    result = compare_acceptance(
        report,
        source_files={"services/app.py": "b" * 64},
        toolchain=tools,
    )
    assert result["invalidated"] is True
    assert result["reasons"] == ["source_hash_mismatch"]


def test_toolchain_change_invalidates_an_acceptance_report():
    tools = {"python": "3.13"}
    report = {
        "source_sha256": {},
        "toolchain": tools,
        "toolchain_sha256": canonical_sha256(tools),
    }
    result = compare_acceptance(
        report,
        source_files={},
        toolchain={"python": "3.14"},
    )
    assert result["invalidated"] is True
    assert result["reasons"] == ["toolchain_changed"]


def test_old_reports_without_toolchain_fingerprint_are_invalidated():
    result = compare_acceptance({}, source_files={}, toolchain={"python": "3.13"})
    assert result["reasons"] == [
        "source_hash_mismatch",
        "toolchain_fingerprint_missing_or_invalid",
    ]
