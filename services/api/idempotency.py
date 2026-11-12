"""Route-level idempotency for authenticated API mutations."""

import base64
import hashlib
import inspect
import json
import re
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import BaseModel


KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{8,128}$")
PENDING_TTL = timedelta(minutes=30)
RESULT_TTL = timedelta(hours=24)
PENDING = {"_idempotency_pending": True}


def _request_fingerprint(kwargs):
    values = {}
    for name, value in kwargs.items():
        if name in {"actor", "idempotency_key"}:
            continue
        if isinstance(value, BaseModel):
            values[name] = value.model_dump(mode="json")
        elif isinstance(value, UUID):
            values[name] = str(value)
        elif isinstance(value, Request):
            names = (
                "content-type",
                "content-length",
                "upload-offset",
                "upload-chunk-sha256",
                "upload-content-sha256",
            )
            values[name] = {header: value.headers.get(header) for header in names}
        elif value is None or isinstance(value, (str, int, float, bool, list, dict)):
            values[name] = value
        else:
            values[name] = str(value)
    encoded = json.dumps(
        values, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _encode_result(result):
    if isinstance(result, Response):
        body = getattr(result, "body", None)
        if body is None:
            raise ValueError("streaming_mutation_response_not_cacheable")
        headers = {
            name.lower(): value
            for name, value in result.headers.items()
            if name.lower()
            in {"content-type", "etag", "x-evidence-graph-sha256", "location"}
        }
        return {
            "kind": "response",
            "status_code": result.status_code,
            "headers": headers,
            "body_base64": base64.b64encode(body).decode("ascii"),
        }
    return {"kind": "json", "value": jsonable_encoder(result)}


def _decode_result(value):
    if value.get("kind") == "response":
        return Response(
            content=base64.b64decode(value["body_base64"]),
            status_code=value["status_code"],
            headers=value.get("headers"),
        )
    return value.get("value")


def idempotent(database, replay, operation):
    """Wrap a FastAPI mutation endpoint with an actor-scoped replay record.

    The route must declare an ``idempotency_key`` parameter using the shared
    ``IdempotencyKey`` header contract. A pending claim prevents concurrent
    duplicate side effects; identical requests briefly wait for the first result,
    and completed JSON/Response results replay for 24 hours.
    """

    # Route-local replay guards may still be present for backward compatibility;
    # keep the generic response cache in a separate namespace.
    operation = f"idempotent-v1:{operation}"

    def decorate(endpoint):
        if "idempotency_key" not in inspect.signature(endpoint).parameters:
            raise TypeError("idempotent_route_requires_idempotency_key_parameter")

        def begin(kwargs):
            key = kwargs["idempotency_key"]
            actor = kwargs.get("actor")
            if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
                raise HTTPException(422, "invalid_idempotency_key")
            if actor is None:
                raise HTTPException(401, "authentication_required")
            body_fingerprint = _request_fingerprint(kwargs)
            deadline = time.monotonic() + 5
            while True:
                pending = False
                with database() as con:
                    con.execute(
                        "DELETE FROM idempotency WHERE expires_at<=?",
                        (datetime.now(timezone.utc).isoformat(),),
                    )
                    scope, fingerprint, previous = replay(
                        con, actor, operation, key, {"fingerprint": body_fingerprint}
                    )
                    if previous is not None:
                        if previous.get("_idempotency_pending"):
                            pending = True
                        else:
                            return None, None, _decode_result(previous)
                    else:
                        expires = (datetime.now(timezone.utc) + PENDING_TTL).isoformat()
                        con.execute(
                            "INSERT INTO idempotency VALUES (?,?,?,?,?,?,?)",
                            (*scope, fingerprint, json.dumps(PENDING), expires),
                        )
                        return scope, fingerprint, None
                if not pending or time.monotonic() >= deadline:
                    raise HTTPException(409, "idempotency_in_progress")
                time.sleep(0.025)

        def finish(scope, fingerprint, result):
            cached = _encode_result(result)
            with database() as con:
                changed = con.execute(
                    "UPDATE idempotency SET response=?,expires_at=? "
                    "WHERE tenant=? AND actor=? AND operation=? AND key_hash=? AND fingerprint=?",
                    (
                        json.dumps(cached, separators=(",", ":")),
                        (datetime.now(timezone.utc) + RESULT_TTL).isoformat(),
                        *scope,
                        fingerprint,
                    ),
                ).rowcount
                if changed != 1:
                    raise HTTPException(503, "idempotency_record_unavailable")

        def abandon(scope, fingerprint):
            with database() as con:
                con.execute(
                    "DELETE FROM idempotency WHERE tenant=? AND actor=? AND operation=? AND key_hash=? AND fingerprint=?",
                    (*scope, fingerprint),
                )

        if inspect.iscoroutinefunction(endpoint):

            @wraps(endpoint)
            async def async_wrapped(*args, **kwargs):
                scope, fingerprint, cached = begin(kwargs)
                if scope is None:
                    return cached
                try:
                    result = await endpoint(*args, **kwargs)
                except BaseException:
                    abandon(scope, fingerprint)
                    raise
                # Keep the pending fence if caching fails after the mutation has
                # committed; a retry must not repeat an uncertain side effect.
                finish(scope, fingerprint, result)
                return result

            return async_wrapped

        @wraps(endpoint)
        def wrapped(*args, **kwargs):
            scope, fingerprint, cached = begin(kwargs)
            if scope is None:
                return cached
            try:
                result = endpoint(*args, **kwargs)
            except BaseException:
                abandon(scope, fingerprint)
                raise
            # Keep the pending fence if caching fails after the mutation has
            # committed; a retry must not repeat an uncertain side effect.
            finish(scope, fingerprint, result)
            return result

        return wrapped

    return decorate
