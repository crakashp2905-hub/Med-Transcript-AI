"""Explicit route authorization inventory; unknown/unguarded routes fail validation."""
from fastapi.routing import APIRoute

PUBLIC = {'/health', '/v1/auth/config', '/v1/auth/login', '/v1/auth/callback'}
DEVELOPMENT = {'/docs', '/redoc', '/openapi.json', '/docs/oauth2-redirect'}
COOKIE_AUTH = {'/v1/auth/session', '/v1/auth/logout'}
STATIC = {'/', '/assets'}


def has_identity(route):
    pending = [route.dependant]
    while pending:
        item = pending.pop()
        if getattr(item.call, '__name__', None) == 'identity':
            return True
        pending.extend(item.dependencies)
    return False


def inventory(app):
    rows = []
    for route in app.routes:
        path = getattr(route, 'path', None)
        if not path:
            continue
        if path in PUBLIC:
            policy = 'public_auth_handshake_or_health'
        elif path in COOKIE_AUTH:
            policy = 'manual_cookie_session_csrf'
        elif path in DEVELOPMENT:
            policy = 'development_only_schema'
        elif path in STATIC:
            policy = 'public_static_application_only'
        elif isinstance(route, APIRoute) and has_identity(route):
            policy = 'authenticated_scoped_identity'
        else:
            raise ValueError('route_has_no_explicit_authorization_policy')
        for method in sorted(getattr(route, 'methods', None) or {'MOUNT'}):
            rows.append({'method': method, 'path': path, 'policy': policy,
                         'optional_if_frontend_unbuilt': path in STATIC})
    return sorted(rows, key=lambda row: (row['path'], row['method']))


def validate(app, expected):
    actual = inventory(app)
    mandatory = [r for r in expected if not r['optional_if_frontend_unbuilt']]
    if any(r not in actual for r in mandatory) or any(r not in expected for r in actual):
        raise ValueError('authorization_policy_contract_changed')
    return {'routes_checked': len(actual), 'real_patient_release_authorized': False}
