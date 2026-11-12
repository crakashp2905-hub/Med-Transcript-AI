from services.interruption_matrix import TRANSITIONS, matrix


def test_interruption_matrix_covers_all_boundaries_and_gates_publication():
    result = matrix()
    assert [row["transition"] for row in result] == list(TRANSITIONS)
    assert all(row["resume_supported"] for row in result)
    assert sum(row["publication_allowed"] for row in result) == 1
