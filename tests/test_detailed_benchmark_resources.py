from services.detailed_benchmark import resource_receipt


def test_resource_receipt_reports_peak_and_fixed_budget_status(monkeypatch):
    monkeypatch.setattr(
        "services.detailed_benchmark.process_peak_resident_bytes",
        lambda: (1024, "test_peak_rss"),
    )

    full = resource_receipt(2048, False)
    resumed = resource_receipt(512, True)

    assert full == {
        "status": "measured",
        "peak_resident_bytes": 1024,
        "method": "test_peak_rss",
        "scope": "benchmark_process_high_water_including_model_load",
        "cohort_scope": "full_process_run",
        "budget_bytes": 2048,
        "budget_status": "within_budget",
    }
    assert resumed["budget_status"] == "exceeded"
    assert resumed["cohort_scope"] == "resumed_suffix"


def test_resource_receipt_keeps_failed_measurement_unverified(monkeypatch):
    def unavailable():
        raise OSError("test_unavailable")

    monkeypatch.setattr(
        "services.detailed_benchmark.process_peak_resident_bytes", unavailable
    )
    result = resource_receipt(4096, False)
    assert result["status"] == "unavailable"
    assert result["peak_resident_bytes"] is None
    assert result["budget_status"] == "unverified"
