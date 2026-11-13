"""Small deterministic diarization challenge cases; not clinical accuracy data."""

from services.diarization_evaluation import score_turns


def challenge_cases():
    """Return turn-swap, interruption, and overlap-miss counterexamples."""
    return [
        {
            "case_id": "turn_swap_last_patient_turn",
            "reference": [
                {"start_ms": a, "end_ms": a + 1000, "role": role}
                for a, role in (
                    (0, "clinician"),
                    (1000, "patient"),
                    (2000, "clinician"),
                    (3000, "patient"),
                )
            ],
            "predicted": [
                {"start_ms": 0, "end_ms": 1000, "speaker_id": "cluster-a"},
                {"start_ms": 1000, "end_ms": 2000, "speaker_id": "cluster-b"},
                {"start_ms": 2000, "end_ms": 3000, "speaker_id": "cluster-a"},
                {"start_ms": 3000, "end_ms": 4000, "speaker_id": "cluster-a"},
            ],
        },
        {
            "case_id": "interruption_missing_patient_overlap",
            "reference": [
                {"start_ms": 0, "end_ms": 1500, "role": "clinician"},
                {"start_ms": 1000, "end_ms": 2000, "role": "patient"},
            ],
            "predicted": [
                {"start_ms": 0, "end_ms": 1500, "speaker_id": "cluster-a"},
                {"start_ms": 1500, "end_ms": 2000, "speaker_id": "cluster-b"},
            ],
        },
        {
            "case_id": "two_person_overlap_collapse",
            "reference": [
                {"start_ms": 0, "end_ms": 1500, "role": "clinician"},
                {"start_ms": 1000, "end_ms": 2000, "role": "patient"},
            ],
            "predicted": [
                {"start_ms": 0, "end_ms": 1500, "speaker_id": "cluster-a"},
                {"start_ms": 1000, "end_ms": 2000, "speaker_id": "cluster-a"},
            ],
        },
    ]


def evaluate_challenges():
    return [
        {
            "case_id": case["case_id"],
            "metrics": score_turns(case["reference"], case["predicted"]),
        }
        for case in challenge_cases()
    ]
