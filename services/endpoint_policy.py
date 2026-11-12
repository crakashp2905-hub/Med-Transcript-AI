"""Provider endpoint safety policy for offline deployments."""

from ipaddress import ip_address
from urllib.parse import urlparse


def validate(url, *, offline=True):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return {"allowed": False, "reason": "invalid_endpoint"}
    host = parsed.hostname.lower()
    if offline and (
        host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local")
    ):
        return {"allowed": False, "reason": "private_destination"}
    try:
        if offline and ip_address(host).is_private:
            return {"allowed": False, "reason": "private_destination"}
    except ValueError:
        pass
    return {"allowed": True, "reason": None}
