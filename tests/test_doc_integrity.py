from services.doc_integrity import scan


def test_documentation_links_and_current_release_claims_are_intact():
    report = scan(".")
    assert report["status"] == "pass", report["broken_links"][:10]
    assert report["claims"] == {
        "wer_gate_5_percent": True,
        "clinical_release_blocked": True,
        "failures_visible": True,
    }
