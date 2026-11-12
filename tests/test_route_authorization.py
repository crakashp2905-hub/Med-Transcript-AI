import pytest

from services.route_authorization import authorize


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("tenant", "tenant_mismatch"),
        ("role", "role_forbidden"),
        ("proposal_owner", "proposal_owner_mismatch"),
    ],
)
def test_route_authorization_blocks_scope_mutations(mutation, expected_reason):
    actor_tenant = resource_tenant = "tenant-a"
    actor_role = "clinician"
    proposal_owner = actor_id = "clinician-a"
    if mutation == "tenant":
        resource_tenant = "tenant-b"
    elif mutation == "role":
        actor_role = "viewer"
    else:
        proposal_owner = "clinician-b"

    result = authorize(
        actor_tenant=actor_tenant,
        resource_tenant=resource_tenant,
        actor_role=actor_role,
        allowed_roles={"clinician"},
        proposal_owner=proposal_owner,
        actor_id=actor_id,
    )
    assert result == {"allowed": False, "reason": expected_reason}
