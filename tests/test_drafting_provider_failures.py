import json
import socket

import pytest

from services.review.providers import JSONProvider


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, limit=-1):
        return self.body[:limit] if limit > 0 else self.body


@pytest.mark.parametrize(
    "failure,body",
    [
        ("timeout", b""),
        ("model_mismatch", None),
        ("malformed_json", b"{"),
        (
            "empty_draft",
            json.dumps(
                {
                    "model": "fixture-model",
                    "choices": [
                        {"message": {"content": json.dumps({"statements": []})}}
                    ],
                }
            ).encode(),
        ),
        ("oversized_response", b"x" * 262145),
    ],
    ids=["timeout", "model-mismatch", "malformed-json", "empty-draft", "oversized"],
)
def test_provider_failure_returns_no_partial_draft(monkeypatch, failure, body):
    if failure == "model_mismatch":
        body = json.dumps(
            {
                "model": "unexpected-model-version",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "statements": [
                                        {
                                            "section": "subjective",
                                            "text": "No fever.",
                                            "fact_ids": ["fact-1"],
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ],
            }
        ).encode()

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))
        ],
    )

    class FakeOpener:
        def open(self, request, timeout):
            if failure == "timeout":
                raise TimeoutError("bounded timeout")
            return Response(body)

    monkeypatch.setattr(
        "services.review.providers.urllib.request.build_opener",
        lambda *handlers: FakeOpener(),
    )
    provider = JSONProvider(
        endpoint="http://127.0.0.1:11434/draft",
        model="fixture-model",
        enabled=True,
        structured_schema=True,
    )
    fact = {
        "fact_id": "fact-1",
        "section": "subjective",
        "text": "No fever.",
        "reviewed": True,
    }

    with pytest.raises(ValueError, match="Provider failed; no output admitted"):
        provider.draft([fact], authorized=True, synthetic=True)
