"""GS-179 Windows route selection preserves the original TLS hostname."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "local"))
from gs179_verified_endpoint import (
    VerifiedAddressHTTPSConnection,
    windows_wifi_ipv4,
    wsl_ipv4,
    wsl_local_backend_origin,
)


class VerifiedEndpointTest(unittest.TestCase):
    def test_current_private_address_only(self):
        runner = lambda *a, **kw: SimpleNamespace(stdout="192.168.1.8\r\n")
        self.assertEqual(windows_wifi_ipv4("https://desktop-3qqu64b.local", runner=runner),
                         "192.168.1.8")
        for output in ("", "192.168.1.8\n192.168.1.9\n", "8.8.8.8\n", "127.0.0.1\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                windows_wifi_ipv4("https://desktop-3qqu64b.local",
                                  runner=lambda *a, **kw: SimpleNamespace(stdout=output))
        with self.assertRaises(ValueError):
            windows_wifi_ipv4("https://untrusted.example",
                              runner=runner)

    def test_route_keeps_sni_hostname(self):
        context = __import__("ssl").create_default_context()
        connection = VerifiedAddressHTTPSConnection(
            "desktop-3qqu64b.local", route_ipv4="192.168.1.8", context=context)
        raw = object()
        tls = object()
        with patch("gs179_verified_endpoint.socket.create_connection", return_value=raw) as create:
            with patch.object(context, "wrap_socket", return_value=tls) as wrap:
                connection.connect()
        create.assert_called_once_with(("192.168.1.8", 443), connection.timeout)
        wrap.assert_called_once_with(raw, server_hostname="desktop-3qqu64b.local")

    def test_wsl_local_route_is_dynamic_and_private(self):
        runner = lambda *a, **kw: SimpleNamespace(
            stdout="2: eth0 inet 172.17.152.10/20 brd 172.17.159.255 scope global eth0\n")
        self.assertEqual(wsl_ipv4(runner=runner), "172.17.152.10")
        for output in ("", "2: eth0 inet 172.17.1.2/20 eth0\n3: eth0 inet 172.17.1.3/20 eth0\n",
                       "2: eth0 inet 8.8.8.8/24 scope global eth0\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                wsl_ipv4(runner=lambda *a, **kw: SimpleNamespace(stdout=output))

    def test_local_listener_route_preserves_original_https_hostname(self):
        self.assertEqual(
            wsl_local_backend_origin("https://desktop-3qqu64b.local", 8444),
            "https://desktop-3qqu64b.local:8444",
        )
        for origin in ("http://desktop-3qqu64b.local", "https://example.com",
                       "https://desktop-3qqu64b.local:9443"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                wsl_local_backend_origin(origin, 8444)
        with self.assertRaises(ValueError):
            wsl_local_backend_origin("https://desktop-3qqu64b.local", 70000)


if __name__ == "__main__":
    unittest.main()
