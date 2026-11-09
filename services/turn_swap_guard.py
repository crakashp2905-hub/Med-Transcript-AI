"""Detect semantic claims whose source speaker changes in synthetic mutations."""


def compare_claim_roles(reference_claims, mutated_claims):
    ref = {item['claim_id']: item.get('role', 'unknown') for item in reference_claims}
    warnings = []
    for item in mutated_claims:
        claim_id, role = item['claim_id'], item.get('role', 'unknown')
        if claim_id in ref and ref[claim_id] != role:
            warnings.append({'claim_id': claim_id, 'from_role': ref[claim_id], 'to_role': role, 'code': 'semantic_role_swap'})
    return {'warnings': warnings, 'approval_blocked': bool(warnings), 'synthetic': True}
