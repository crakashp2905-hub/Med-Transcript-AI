import pytest
from services.stage_timing import STAGES, StageTimer


def test_stage_timer_is_failure_inclusive_and_complete_only_when_every_stage_succeeds():
    timer = StageTimer()
    timer.measure("transfer", lambda: "ok")
    with pytest.raises(RuntimeError):
        timer.measure(
            "asr", lambda: (_ for _ in ()).throw(RuntimeError("synthetic failure"))
        )
    timer.mark_unavailable("recording", "synthetic_fixture")
    report = timer.report()
    assert tuple(report["stages"]) == STAGES
    assert report["stages"]["transfer"]["status"] == "succeeded"
    assert report["stages"]["asr"]["status"] == "failed"
    assert report["stages"]["recording"]["status"] == "unavailable"
    assert report["complete"] is False


def test_stage_timer_rejects_unknown_stage_and_missing_unavailable_reason():
    timer = StageTimer()
    with pytest.raises(ValueError):
        timer.measure("unknown", lambda: None)
    with pytest.raises(ValueError):
        timer.mark_unavailable("asr", "")
