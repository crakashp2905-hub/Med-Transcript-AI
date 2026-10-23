"""Run the synthetic demo with a Python-level external-network guard, not an OS firewall."""

import json
import runpy
import socket
import sys


def main():
    original_connect, original_getaddrinfo = socket.socket.connect, socket.getaddrinfo
    attempts = []

    def local_host(host):
        return host in ("localhost", "127.0.0.1", "::1")

    def guarded_connect(sock, address):
        if isinstance(address, tuple) and not local_host(address[0]):
            attempts.append("external_connect")
            raise RuntimeError("External networking blocked for synthetic offline smoke")
        return original_connect(sock, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not local_host(host):
            attempts.append("external_dns")
            raise RuntimeError("External DNS blocked for synthetic offline smoke")
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect, socket.getaddrinfo = guarded_connect, guarded_getaddrinfo
    try:
        sys.argv[0] = "services.demo_ingest"
        runpy.run_module("services.demo_ingest", run_name="__main__")
    finally:
        socket.socket.connect, socket.getaddrinfo = original_connect, original_getaddrinfo
    print(json.dumps({"python_socket_guard": "external_network_blocked", "blocked_attempts": len(attempts)}))


if __name__ == "__main__":
    main()
