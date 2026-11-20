from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_investor_preview_uses_synthetic_source_fixture_without_api_calls():
    component = (ROOT / "apps/clinician-web/src/InvestorDemo.tsx").read_text(
        encoding="utf-8"
    )
    entrypoint = (ROOT / "apps/clinician-web/src/main.tsx").read_text(encoding="utf-8")
    assert "synthetic-investor-preview-v1" in component
    assert "synthetic:true" in component
    assert "data/demo-sample.json" not in component
    assert "Investor preview · read only · no sign-in" in component
    assert "NOT CLINICALLY APPROVED" in component
    assert 'aria-label="Not clinically approved investor demo"' in component
    assert "does not process audio" in component
    assert "fetch(" not in component and "/v1/" not in component
    assert "window.location.pathname==='/investor-demo'" in entrypoint


def test_investor_demo_route_serves_only_frontend_entrypoint():
    main = (ROOT / "services/api/main.py").read_text(encoding="utf-8")
    route = main.split('@app.get("/investor-demo", include_in_schema=False)', 1)[1]
    route = route.split("return app", 1)[0]

    assert 'return FileResponse(frontend / "index.html")' in route
    assert "Depends(identity)" not in route
