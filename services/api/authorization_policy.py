"""Explicit route authorization inventory; unknown/unguarded routes fail validation."""

from fastapi.routing import APIRoute
import re

PUBLIC = {"/health", "/v1/auth/config", "/v1/auth/login", "/v1/auth/callback"}
DEVELOPMENT = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
COOKIE_AUTH = {"/v1/auth/session", "/v1/auth/logout"}
STATIC = {"/", "/assets", "/investor-demo"}


def has_identity(route):
    pending = [route.dependant]
    while pending:
        item = pending.pop()
        if getattr(item.call, "__name__", None) == "identity":
            return True
        pending.extend(item.dependencies)
    return False


def inventory(app):
    rows = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        if path in PUBLIC:
            policy = "public_auth_handshake_or_health"
        elif path in COOKIE_AUTH:
            policy = "manual_cookie_session_csrf"
        elif path in DEVELOPMENT:
            policy = "development_only_schema"
        elif path in STATIC:
            policy = "public_static_application_only"
        elif isinstance(route, APIRoute) and has_identity(route):
            policy = "authenticated_scoped_identity"
        else:
            raise ValueError("route_has_no_explicit_authorization_policy")
        for method in sorted(getattr(route, "methods", None) or {"MOUNT"}):
            rows.append(
                {
                    "method": method,
                    "path": path,
                    "policy": policy,
                    "optional_if_frontend_unbuilt": path in STATIC,
                }
            )
    return sorted(rows, key=lambda row: (row["path"], row["method"]))


def validate(app, expected):
    actual = inventory(app)
    mandatory = [r for r in expected if not r["optional_if_frontend_unbuilt"]]
    if any(r not in actual for r in mandatory) or any(
        r not in expected for r in actual
    ):
        raise ValueError("authorization_policy_contract_changed")
    documented = app.openapi().get("paths", {})
    openapi_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
    operations = {
        (method.upper(), path): operation
        for path, path_item in documented.items()
        for method, operation in path_item.items()
        if method in openapi_methods
    }
    runtime_operations = {
        (row["method"], row["path"])
        for row in actual
        if row["path"].startswith(("/health", "/v1/"))
        and row["method"] in {method.upper() for method in openapi_methods}
    }
    if runtime_operations != set(operations):
        raise ValueError("openapi_route_coverage_mismatch")

    policies = {(row["method"], row["path"]): row["policy"] for row in actual}
    operation_ids = set()
    path_parameters_checked = 0
    for key, operation in operations.items():
        policy = policies.get(key)
        if (
            not isinstance(operation, dict)
            or not isinstance(operation.get("responses"), dict)
            or not operation["responses"]
        ):
            raise ValueError("openapi_operation_schema_incomplete")
        operation_id = operation.get("operationId")
        if (
            not isinstance(operation_id, str)
            or not operation_id
            or operation_id in operation_ids
        ):
            raise ValueError("openapi_operation_id_invalid")
        operation_ids.add(operation_id)
        secured = bool(operation.get("security"))
        if policy == "authenticated_scoped_identity" and not secured:
            raise ValueError("authenticated_route_missing_openapi_security")
        if (
            policy in {"public_auth_handshake_or_health", "development_only_schema"}
            and secured
        ):
            raise ValueError("public_route_declares_unexpected_security")
        required_parameters = set(re.findall(r"\{([^}]+)\}", key[1]))
        declared_parameters = {
            parameter.get("name")
            for parameter in operation.get("parameters", [])
            if parameter.get("in") == "path" and parameter.get("required") is True
        }
        if required_parameters - declared_parameters:
            raise ValueError("openapi_path_parameter_contract_incomplete")
        path_parameters_checked += len(required_parameters)
    return {
        "routes_checked": len(actual),
        "openapi_operations_checked": len(operations),
        "authenticated_operations_checked": sum(
            policy == "authenticated_scoped_identity" for policy in policies.values()
        ),
        "operation_schema_contracts_checked": len(operations),
        "path_parameters_checked": path_parameters_checked,
        "real_patient_release_authorized": False,
    }
