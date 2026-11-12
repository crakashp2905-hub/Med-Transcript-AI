"""Opt-in Python network denial for offline research; not an OS sandbox."""

import ipaddress
import os
import socket

_installed = False


class OfflineNetworkDenied(OSError):
    pass


def loopback(host):
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="strict")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def install():
    global _installed
    if _installed:
        return
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_lookup = socket.getaddrinfo
    original_sendto = socket.socket.sendto

    def check(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and (
            not isinstance(address, tuple) or not loopback(address[0])
        ):
            raise OfflineNetworkDenied("offline_non_loopback_network_denied")
        if sock.family in (socket.AF_INET, socket.AF_INET6) and address[0] in (
            "localhost",
            b"localhost",
        ):
            address = (
                ("::1" if sock.family == socket.AF_INET6 else "127.0.0.1"),
                *address[1:],
            )
        return address

    def connect(sock, address):
        return original_connect(sock, check(sock, address))

    def connect_ex(sock, address):
        return original_connect_ex(sock, check(sock, address))

    def lookup(host, *args, **kwargs):
        if not loopback(host):
            raise OfflineNetworkDenied("offline_dns_denied")
        if host in ("localhost", b"localhost"):
            family = (
                args[1] if len(args) > 1 else kwargs.get("family", socket.AF_UNSPEC)
            )
            host = "::1" if family == socket.AF_INET6 else "127.0.0.1"
        rows = original_lookup(host, *args, **kwargs)
        if any(not loopback(row[4][0]) for row in rows):
            raise OfflineNetworkDenied("offline_dns_rebinding_denied")
        return rows

    def sendto(sock, data, *args):
        return original_sendto(sock, data, *args[:-1], check(sock, args[-1]))

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = lookup
    socket.socket.sendto = sendto
    for name in ("gethostbyname", "gethostbyname_ex", "gethostbyaddr"):

        def guarded(host, _name=name):
            if not loopback(host):
                raise OfflineNetworkDenied("offline_dns_denied")
            address = "127.0.0.1" if host in ("localhost", b"localhost") else host
            return address if _name == "gethostbyname" else ("localhost", [], [address])

        setattr(socket, name, guarded)
    if hasattr(socket.socket, "sendmsg"):
        original_sendmsg = socket.socket.sendmsg

        def sendmsg(sock, buffers, ancdata=(), flags=0, address=None):
            if address is not None:
                address = check(sock, address)
            return original_sendmsg(sock, buffers, ancdata, flags, address)

        socket.socket.sendmsg = sendmsg
    for name in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        os.environ[name] = "1"
    _installed = True


def validate_profile():
    if os.getenv("MED_TRANSCRIPT_PROFILE") != "no_external_dependency":
        return
    if os.getenv("MED_TRANSCRIPT_OFFLINE") != "1":
        raise ValueError("no_external_dependency requires MED_TRANSCRIPT_OFFLINE=1")
    if os.getenv("MED_TRANSCRIPT_AUTH_MODE", "local") != "local":
        raise ValueError("live_oauth_forbidden_in_offline_profile")
    if os.getenv("MED_TRANSCRIPT_DRAFTING_MODE", "deterministic") == "hosted":
        raise ValueError("hosted_inference_forbidden_in_offline_profile")
    install()
