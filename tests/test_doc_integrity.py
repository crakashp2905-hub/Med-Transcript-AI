from services.doc_integrity import scan


def test_documentation_links_and_current_release_claims_are_intact():
    report = scan(".")
    assert report["status"] == "pass", report["broken_links"][:10]
    assert report["claims"] == {
        "wer_gate_5_percent": True,
        "clinical_release_blocked": True,
        "failures_visible": True,
    }
    assert report["source_references"]
    assert report["test_references"]
    assert report["api_examples"]
    assert report["broken_source_references"] == []
    assert report["broken_test_references"] == []
    assert report["broken_api_examples"] == []


def test_document_integrity_finds_broken_links_paths_test_names_and_api_examples(
    tmp_path,
):
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "services").mkdir()
    (tmp_path / "README.md").write_text(
        "5% Real-patient release is not authorized; failures remain visible.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/guide.md").write_text(
        """[missing file](absent.md) [missing anchor](../README.md#absent)

`services/missing.py` `test_missing_example`

```http
GET /missing-route
```
""",
        encoding="utf-8",
    )
    (tmp_path / "services/api.py").write_text(
        'def register(app):\n    @app.get("/health")\n    def health():\n        return {}\n',
        encoding="utf-8",
    )
    report = scan(tmp_path)
    assert report["status"] == "fail"
    assert {item["reason"] for item in report["broken_links"]} == {
        "target_missing",
        "anchor_missing",
    }
    assert [item["target"] for item in report["broken_source_references"]] == [
        "services/missing.py"
    ]
    assert [item["target"] for item in report["broken_test_references"]] == [
        "test_missing_example"
    ]
    assert [item["path"] for item in report["broken_api_examples"]] == [
        "/missing-route"
    ]
