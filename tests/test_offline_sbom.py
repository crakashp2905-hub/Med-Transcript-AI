from datetime import datetime, timezone

from services.offline_sbom import advisory_freshness, build_sbom


def test_sbom_lists_installed_packages_and_never_calls_unscanned_packages_safe():
    report = build_sbom(
        project={
            "name": "med-transcript-ai",
            "version": "0.4",
            "dependencies": ["FastAPI>=1"],
            "optional-dependencies": {},
        },
        constraints="fastapi==1.2.3\nrequests==2.0.0\n",
        distributions=[("fastapi", "1.2.3"), ("local-extra", "4.0")],
        source_commit="a" * 40,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert report["redacted"] is True
    assert report["components"][0]["inventory_status"] == "pinned_match"
    assert report["offline_dependency_inventory"]["missing_pinned_packages"] == [
        "requests"
    ]
    assert report["advisory_database"]["status"] == "unavailable"
    assert report["vulnerability_assessment"]["status"] == "not_performed"
    assert report["vulnerability_assessment"]["safe_to_use"] is None


def test_advisory_freshness_reports_age_from_local_timestamp(tmp_path):
    cache = tmp_path / "advisories.json"
    cache.write_text('{"fetched_at":"2025-12-30T00:00:00Z"}', encoding="utf-8")
    result = advisory_freshness(cache, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert result["status"] == "available_metadata_only"
    assert result["age_days"] == 2.0
