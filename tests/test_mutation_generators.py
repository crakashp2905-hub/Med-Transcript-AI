from services.mutation_generators import generate


def test_mutation_generator_declares_kind_and_synthetic_scope():
    result = generate(['f1'], 'single')
    assert result['one_change_at_a_time'] is True
    assert result['clinical_gold'] is False
