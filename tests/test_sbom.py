from services.sbom import generate


def test_sbom_contains_pinned_components_and_distinguishes_audit_status():
    value = generate(".")
    assert value["bomFormat"] == "CycloneDX" and value["components"]
    assert any(
        item["name"] == "fastapi" and item["version"] for item in value["components"]
    )
    assert value["audit_status"] == "not_run_without_tooling"
