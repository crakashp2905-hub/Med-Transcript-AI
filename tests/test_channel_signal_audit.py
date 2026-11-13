import wave
import pytest

np = pytest.importorskip("numpy")
from services.channel_signal_audit import audit  # noqa: E402


def test_distinct_channels_pass_but_swap_and_crosstalk_fail(tmp_path):
    rate = 16000
    time = np.arange(rate * 2) / rate
    samples = np.stack(
        [0.3 * np.sin(2 * np.pi * f * time) for f in (220, 440, 660)], axis=1
    )

    def write(name, values):
        path = tmp_path / name
        with wave.open(str(path), "wb") as audio:
            audio.setparams((3, 2, rate, 0, "NONE", "not compressed"))
            audio.writeframes((values * 32767).astype("<i2").tobytes())
        return path

    report = audit(write("clean.wav", samples), [220, 440, 660], -30, 2)
    assert report["signal_checks_pass"] and not report["physical_hardware_validated"]
    assert all(
        row["cross_talk_status"] == "clear_within_supplied_tolerance"
        for row in report["channels"]
    )
    assert not audit(write("swapped.wav", samples[:, [1, 0, 2]]), [220, 440, 660], -30)[
        "signal_checks_pass"
    ]
    contaminated = samples.copy()
    contaminated[:, 0] += samples[:, 1] * 0.5
    leak_report = audit(write("leak.wav", contaminated), [220, 440, 660], -30)
    assert not leak_report["signal_checks_pass"]
    assert leak_report["channels"][0]["cross_talk_status"] == (
        "unknown_energy_correlation_disagree"
    )
    assert leak_report["channels"][0]["maximum_absolute_channel_correlation"] < 0.95
