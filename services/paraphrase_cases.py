"""Legitimate paraphrase scenarios kept distinct from adversarial prompts."""


def scenarios():
    return [
        {
            "id": "paraphrase-1",
            "source": "Continue current medication.",
            "paraphrase": "Keep taking the existing medicine.",
            "adversarial": False,
        },
        {
            "id": "paraphrase-2",
            "source": "Follow up in two weeks.",
            "paraphrase": "Return for review after 14 days.",
            "adversarial": False,
        },
    ]
