from services.route_authorization import authorize


def test_route_authorization_blocks_cross_tenant_and_cross_role_access():
    assert authorize(actor_tenant='a', resource_tenant='b', actor_role='clinician', allowed_roles={'clinician'}, proposal_owner='u', actor_id='u')['reason'] == 'tenant_mismatch'
    assert authorize(actor_tenant='a', resource_tenant='a', actor_role='viewer', allowed_roles={'clinician'}, proposal_owner='u', actor_id='u')['reason'] == 'role_forbidden'
    assert authorize(actor_tenant='a', resource_tenant='a', actor_role='clinician', allowed_roles={'clinician'}, proposal_owner='other', actor_id='u')['reason'] == 'proposal_owner_mismatch'
