"""Study dashboard data contract with honest failure and admission fields."""


def build(*, datasets, variants):
    if not isinstance(datasets, list) or not isinstance(variants, list):
        raise ValueError("datasets_and_variants_required")
    return {
        "datasets": datasets,
        "variants": variants,
        "visible_failures": True,
        "cost_claim": None,
        "accuracy_claim": None,
        "model_not_admitted_banner": True,
    }
