from services.asr.spoken_prompt_adversarial import PROMPT_TEXT
from services.prompt_injection import inspect


def test_spoken_prompt_challenge_keeps_transcript_inert_as_source_data():
    result = inspect(PROMPT_TEXT)
    assert result["untrusted"] is True
    assert result["application_control"] is False
    assert result["file_access"] is False
    assert result["approval_control"] is False
    assert set(result["markers"]) == {
        "approve the note",
        "ignore previous instructions",
        "read file",
    }
