from services.module_catalog import LABELS, build_catalog, render


def test_module_catalog_accounts_for_every_service_and_discovers_endpoints():
    catalog = build_catalog()
    assert catalog["modules"]
    assert set(catalog["classification_counts"]) <= set(LABELS)
    assert sum(catalog["classification_counts"].values()) == len(catalog["modules"])
    assert any(
        route["path"] == "/v1/encounters/{eid}/approvals"
        for route in catalog["endpoints"]
    )
    assert any(
        module["module"] == "services.api.main"
        and module["classification"] == "integrated-in-production-flow"
        for module in catalog["modules"]
    )


def test_committed_service_catalog_matches_source_generator():
    from pathlib import Path

    assert Path("docs/service-catalog.md").read_text(encoding="utf-8") == render(
        build_catalog()
    )
