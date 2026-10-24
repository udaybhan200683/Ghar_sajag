"""GS-179 Windows route selection preserves the original TLS hostname."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "local"))
from gs179_verified_endpoint import VerifiedAddressHTTPSConnection, windows_wifi_ipv4


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


if __name__ == "__main__":
    unittest.main()
