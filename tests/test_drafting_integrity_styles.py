import json
import socket

import pytest

from services.note_style import STYLES, apply
from services.review.providers import DeterministicProvider, JSONProvider, validate


FACTS = [
    {
        "fact_id": "dose",
        "section": "plan",
        "text": "Take warfarin 5 mg orally twice daily.",
        "reviewed": True,
    },
    {
        "fact_id": "negation",
        "section": "subjective",
        "text": "Patient denies fever.",
        "reviewed": True,
    },
    {
        "fact_id": "unit",
        "section": "plan",
        "text": "Taking insulin 5 units.",
        "reviewed": True,
    },
    {
        "fact_id": "time",
        "section": "subjective",
        "text": "Previously stopped metformin.",
        "reviewed": True,
    },
    {
        "fact_id": "subject",
        "section": "subjective",
        "text": "Mother has diabetes.",
        "reviewed": True,
    },
]


class _Response:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, limit=-1):
        return self.value[:limit] if limit > 0 else self.value


@pytest.mark.parametrize("mode", ["local", "hosted"])
def test_json_adapters_keep_clinical_literals_with_fake_transport(monkeypatch, mode):
    statements = [
        {
            "section": fact["section"],
            "text": fact["text"],
            "fact_ids": [fact["fact_id"]],
        }
        for fact in FACTS
    ]
    envelope = json.dumps(
        {
            "model": "fixture-model",
            "choices": [
                {"message": {"content": json.dumps({"statements": statements})}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
    ).encode()

    class FakeOpener:
        def open(self, request, timeout):
            assert timeout <= 60
            return _Response(envelope)

    def fake_getaddrinfo(host, port, *args, **kwargs):
        address = "127.0.0.1" if host == "127.0.0.1" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(
        "services.review.providers.urllib.request.build_opener",
        lambda *handlers: FakeOpener(),
    )
    provider = JSONProvider(
        endpoint=(
            "http://127.0.0.1:11434/draft"
            if mode == "local"
            else "https://provider.test/draft"
        ),
        model="fixture-model",
        mode=mode,
        enabled=True,
        allowed_hosts=("provider.test",) if mode == "hosted" else (),
        api_key="fake-test-only" if mode == "hosted" else "",
        billing_cap_confirmed=mode == "hosted",
        structured_schema=True,
    )

    result = provider.draft(FACTS, authorized=True, synthetic=True)

    assert result["findings"] == []
    assert [row["text"] for row in result["draft"]["statements"]] == [
        fact["text"] for fact in FACTS
    ]
    if mode == "local":
        assert result["provenance"]["provider_cost_usd"] == 0
    else:
        assert result["provenance"]["cost"] is None
        assert (
            result["provenance"]["cost_status"] == "requires_verified_provider_pricing"
        )


@pytest.mark.parametrize("style", sorted(STYLES))
def test_note_styles_preserve_dose_negation_unit_timing_and_subject(style):
    draft = DeterministicProvider().draft(FACTS, authorized=True, synthetic=True)
    styled = apply(draft["draft"], style)

    assert styled["source_facts_preserved"] is True
    assert styled["evidence_preserved"] is True
    assert styled["semantic_mutation"] is False
    assert [row["text"] for row in styled["statements"]] == [
        fact["text"] for fact in FACTS
    ]


@pytest.mark.parametrize(
    "source,claim,expected_code",
    [
        (
            "Take warfarin 5 mg orally twice daily.",
            "Take warfarin 50 mg orally twice daily.",
            "dose_or_unit_disagreement",
        ),
        (
            "Patient denies fever.",
            "Patient has fever.",
            "negation_disagreement",
        ),
        (
            "Taking insulin 5 units.",
            "Taking insulin 5 mg.",
            "dose_or_unit_disagreement",
        ),
        (
            "Previously stopped metformin.",
            "Currently taking metformin.",
            "temporality_disagreement",
        ),
        (
            "Mother has diabetes.",
            "Patient has diabetes.",
            "incorrect_attribution",
        ),
    ],
)
def test_provider_independent_gate_blocks_critical_literal_mutations(
    source, claim, expected_code
):
    result = validate(
        {
            "statements": [
                {"section": "subjective", "text": claim, "fact_ids": ["fact-1"]}
            ]
        },
        [
            {
                "fact_id": "fact-1",
                "section": "subjective",
                "text": source,
                "reviewed": True,
            }
        ],
    )

    assert expected_code in {finding["code"] for finding in result["findings"]}
    assert result["status"] == "review_required"
