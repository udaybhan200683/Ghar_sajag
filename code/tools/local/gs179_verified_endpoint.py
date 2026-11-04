"""Route TEST_ONLY .local HTTPS through a measured IPv4 without changing TLS identity."""
from __future__ import annotations

import http.client
import hashlib
import ipaddress
from pathlib import Path
import re
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


def verify_caregiver_origin_alias(canonical_origin: str, apk_origin: str,
                                 ca_file: Path, server_cert_file: Path, *,
                                 wifi_address_reader=None, connection_factory=None) -> dict:
    """Verify TEST_ONLY DNS/IP aliases of the same installed HTTPS endpoint.

    A private address or matching certificate SAN alone does not grant an alias.
    The APK address must be the measured current Wi-Fi address, and both names
    must pass the existing CA/hostname policy and serve the installed leaf.
    """
    def origin_host(value):
        if not isinstance(value, str):
            raise ValueError("invalid_caregiver_https_origin")
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.username is not None or
                parsed.password is not None or not parsed.hostname or
                parsed.port not in (None, 443) or parsed.path not in ("", "/") or
                parsed.query or parsed.fragment):
            raise ValueError("invalid_caregiver_https_origin")
        return parsed.hostname

    canonical_host = origin_host(canonical_origin)
    if not re.fullmatch(r"[a-z0-9-]+\.local", canonical_host):
        raise ValueError("canonical_test_only_local_origin_required")
    apk_host = origin_host(apk_origin)
    try:
        address = ipaddress.IPv4Address(apk_host)
    except ipaddress.AddressValueError:
        raise ValueError("apk_alias_must_be_current_private_ipv4") from None
    if not any(address in ipaddress.IPv4Network(network) for network in
               ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")):
        raise ValueError("apk_alias_must_be_current_private_ipv4")
    reader = wifi_address_reader or windows_wifi_ipv4
    route = reader(canonical_origin)
    if str(address) != route:
        raise ValueError("apk_origin_is_not_current_windows_wifi_address")
    context = ssl.create_default_context(cafile=str(ca_file))
    installed_der = ssl.PEM_cert_to_DER_cert(Path(server_cert_file).read_text())
    expected_hash = hashlib.sha256(installed_der).hexdigest()
    factory = connection_factory or VerifiedAddressHTTPSConnection
    for host in (canonical_host, apk_host):
        connection = factory(host, route_ipv4=route, context=context, timeout=3)
        try:
            connection.connect()
            peer = connection.sock.getpeercert(binary_form=True)
            if not peer or hashlib.sha256(peer).hexdigest() != expected_hash:
                raise ValueError("caregiver_alias_installed_server_certificate_mismatch")
        finally:
            connection.close()
    return {"profile": "GS179_TEST_ONLY", "method": "CA_HOSTNAME_AND_SAME_INSTALLED_LEAF",
            "canonical_origin": "https://" + canonical_host,
            "apk_origin": "https://" + apk_host,
            "route_ipv4": route, "server_cert_sha256": expected_hash}


def physical_ingress_authority(approval_ref, controller_pid, service_directory):
    """Read existing DEV authority and bounded launcher receipts; never reserve it.

    This is a projection for the Windows network utility, not hardware consent.
    A network session cannot renew the DEV scope or start/restart its services.
    """
    import json
    import os
    import stat
    import gs117_hil_authorization as auth

    def private_json(path):
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_mode & 0o077):
            raise ValueError("physical_session_receipt_not_private")
        return json.loads(path.read_text())

    policy = auth.load_development()
    if (policy['owner_approval_ref'] != approval_ref or
            policy['procedures'] != ['protected_gs40_bootstrap'] or
            policy.get('max_sessions') != 1 or policy.get('max_retries') != 0 or
            policy.get('observation_seconds') != 90 or
            policy.get('max_bootstraps_per_session') != 1 or
            policy.get('motion_injection_authorized') is not False):
        raise ValueError('physical_session_authorization_scope_mismatch')
    status = auth.development_status()
    if status['status'] != 'ACTIVE':
        # A reserved session is pessimistically blocked until completion. Admit
        # only its live lock holder, with no failure, during its bounded child.
        ledger, _ = auth._development_ledger_path(auth.DEV_STATE, policy)
        row = private_json(ledger)
        import fcntl
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(row['started_at'])).total_seconds()
        with (auth.DEV_STATE / 'session.lock').open('r') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                held = True
            else:
                held = False
        if (not held or row.get('failure') or row.get('completed_at') or
                row.get('procedure') != 'protected_gs40_bootstrap' or not 0 <= age <= 150):
            raise ValueError('physical_session_authorization_ended')
    proc = Path('/proc') / str(int(controller_pid))
    if proc.stat().st_uid != os.getuid():
        raise ValueError('physical_session_controller_owner_mismatch')
    controller_start = proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]
    if proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z':
        raise ValueError('physical_session_controller_exited')
    directory = Path(service_directory)
    allowed = Path.home() / '.local/state/ghar-sajag/gs117-tc001'
    if (directory.is_symlink() or directory.parent.resolve() != allowed.resolve() or
            directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077):
        raise ValueError('physical_session_service_directory_invalid')
    manifest = private_json(directory / 'launch-manifest.json')
    process = next(p for p in manifest['processes'] if p['script'] == 'gs117-active-ingress.py')
    script = directory / process['script']
    if script.is_symlink() or hashlib.sha256(script.read_bytes()).hexdigest() != process['sha256']:
        raise ValueError('physical_session_service_script_changed')
    ingress_proc = Path('/proc') / str(int(process['pid']))
    if (ingress_proc.stat().st_uid != os.getuid() or
            str(script).encode() not in ingress_proc.joinpath('cmdline').read_bytes().split(b'\0')):
        raise ValueError('physical_session_service_identity_mismatch')
    runtime = private_json(directory / 'ingress-runtime-status.json')
    from datetime import datetime, timezone
    if (runtime['pid'] != process['pid'] or
            not 0 <= (datetime.now(timezone.utc) - datetime.fromisoformat(runtime['at'])).total_seconds() <= 10 or
            any(runtime['status'].get(key) != 'YES' for key in
                ('listener_ready', 'postgres_ready', 'trusted_time_ready')) or
            runtime['status'].get('profile') != 'GS179_TEST_ONLY'):
        raise ValueError('physical_session_service_expired_or_unready')
    return {'approval_ref': approval_ref, 'scope_id': status['authorization_scope_id'],
            'activation': policy['development_mode']['activation_id'],
            'controller_start': controller_start, 'wsl_address': wsl_ipv4(),
            'service_pid': process['pid'],
            'service_start': ingress_proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19],
            'service_sha256': process['sha256']}


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--physical-ingress-authority', required=True)
    parser.add_argument('--controller-pid', required=True, type=int)
    parser.add_argument('--service-directory', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(physical_ingress_authority(
            args.physical_ingress_authority, args.controller_pid, args.service_directory)))
    except Exception as error:
        print(json.dumps({'error': type(error).__name__}))
        raise SystemExit(2)
