from services.component_ablation import COMPONENTS, configure


def test_component_ablation_exposes_each_novel_component():
    result = configure(**{component: True for component in COMPONENTS})
    assert set(result['components']) == set(COMPONENTS)
    assert result['active_count'] == len(COMPONENTS)
