"""Route TEST_ONLY .local HTTPS through a measured IPv4 without changing TLS identity."""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import subprocess
from urllib.parse import urlsplit, urlunsplit
import urllib.request


def windows_wifi_ipv4(origin: str, *, runner=subprocess.run) -> str:
    host = urlsplit(origin).hostname
    if not host or not host.endswith(".local") or host.count(".") != 1:
        raise ValueError("expected_single_label_test_only_local_origin")
    command = [
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "-NoProfile", "-NonInteractive", "-Command",
        'Get-NetIPAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4 | '
        'Where-Object { $_.AddressState -eq "Preferred" } | '
        'Select-Object -ExpandProperty IPAddress',
    ]
    result = runner(command, capture_output=True, text=True, timeout=8, check=True)
    addresses = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(addresses) != 1:
        raise ValueError("one_current_windows_wifi_ipv4_required")
    address = ipaddress.ip_address(addresses[0])
    if not isinstance(address, ipaddress.IPv4Address) or not address.is_private or address.is_loopback:
        raise ValueError("windows_wifi_ipv4_must_be_private")
    return str(address)


def wsl_ipv4(*, interface: str = "eth0", runner=subprocess.run) -> str:
    """Return the current WSL backend address without using cached Wi-Fi state."""
    if not isinstance(interface, str) or not interface or not interface.isascii():
        raise ValueError("invalid_wsl_interface")
    result = runner(["ip", "-4", "-o", "addr", "show", "dev", interface],
                    capture_output=True, text=True, timeout=5, check=True)
    addresses = []
    for line in result.stdout.splitlines():
        fields = line.split()
        try:
            marker = fields.index("inet")
            addresses.append(fields[marker + 1].split("/", 1)[0])
        except (ValueError, IndexError):
            continue
    if len(addresses) != 1:
        raise ValueError("one_current_wsl_ipv4_required")
    address = ipaddress.ip_address(addresses[0])
    if (not isinstance(address, ipaddress.IPv4Address) or not address.is_private or
            address.is_loopback or address.is_link_local):
        raise ValueError("wsl_ipv4_must_be_private_unicast")
    return str(address)


def wsl_local_backend_origin(origin: str, port: int) -> str:
    """Select the existing local listener while preserving TLS hostname/SNI."""
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or parsed.username is not None or
            parsed.password is not None or parsed.hostname is None or
            not parsed.hostname.endswith(".local") or parsed.path or
            parsed.query or parsed.fragment or parsed.port is not None):
        raise ValueError("expected_bare_test_only_https_local_origin")
    if type(port) is not int or not 1 <= port <= 65_535:
        raise ValueError("local_backend_port_out_of_bounds")
    return urlunsplit(("https", f"{parsed.hostname}:{port}", "", "", ""))


class VerifiedAddressHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *, route_ipv4: str, context: ssl.SSLContext, **kwargs):
        super().__init__(host, context=context, **kwargs)
        self.route_ipv4 = route_ipv4

    def connect(self) -> None:
        # The socket route is an address hint only. SNI and hostname validation
        # remain bound to self.host and the caller's trusted CA.
        raw = socket.create_connection((self.route_ipv4, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class VerifiedAddressHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, context: ssl.SSLContext, route_ipv4: str):
        super().__init__(context=context)
        self.route_ipv4 = route_ipv4
        self.context = context

    def https_open(self, request):
        return self.do_open(
            lambda host, **kw: VerifiedAddressHTTPSConnection(
                host, route_ipv4=self.route_ipv4, context=self.context, **kw),
            request,
        )
