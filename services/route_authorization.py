"""Source-level tenant, role, and proposal ownership authorization."""


def authorize(*, actor_tenant, resource_tenant, actor_role, allowed_roles, proposal_owner, actor_id):
    if actor_tenant != resource_tenant:
        return {'allowed': False, 'reason': 'tenant_mismatch'}
    if actor_role not in allowed_roles:
        return {'allowed': False, 'reason': 'role_forbidden'}
    if proposal_owner != actor_id:
        return {'allowed': False, 'reason': 'proposal_owner_mismatch'}
    return {'allowed': True, 'reason': None}
