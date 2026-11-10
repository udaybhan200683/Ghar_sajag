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


# Source-reviewed owner approval snapshots. These pins are evidence of the
# current two-window grant, not a general string-based consent issuer.
NETWORK_APPROVAL_PINS = {
    'GS-117#11910': '2a41347dc380d05642c7f409b61e2eb43454cc365f7e6316831cba5d9cd2daa9',
    'GS-179#11911': '0b55b62765af17c7792a314820e4d78b1540ddcb4581b13161ef3dfef13beb47',
}
NETWORK_OWNER = '712020:d1785a8a-5bf2-4556-a451-0805ddb6af74'
DEV_NETWORK_APPROVAL_PINS = {
    'GS-179#11916': '3028184134ebd78e5d6a9f0b6879f3cc7ea35acd98f3926290e45a464895f711',
    'GS-117#11917': 'fab63d513982653ce2155834c8e170d7cc1f0936917a1db7bad58184f6c43111',
}
DEV_NETWORK_SECONDS = 432000
NETWORK_IDLE_SECONDS = 1800


def _network_utc(now=None):
    from datetime import datetime, timezone
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError('network_clock_not_utc')
    return value


def _network_event(event, **fields):
    import gs117_hil_authorization as auth
    record = dict(event=event, at_utc=_network_utc().isoformat(), **fields)
    record['record_sha256'] = auth._canonical_record_sha256(record)
    auth._append_private_audit(auth.DEV_MODE_AUDIT, record)


def _network_write_once(path, record):
    import os, json
    raw = (json.dumps(record, sort_keys=True) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw); out.flush(); os.fsync(out.fileno())
    return hashlib.sha256(raw).hexdigest()


def record_development_network_authorization(comments, *, now=None):
    """Issue this reviewed five-day consent ONCE; never change hardware consent."""
    import os, fcntl
    from datetime import timedelta
    import gs117_hil_authorization as auth
    if (set(comments) != set(DEV_NETWORK_APPROVAL_PINS) or
            any(c.get('author') != NETWORK_OWNER or
                hashlib.sha256(c.get('body', '').encode()).hexdigest() != DEV_NETWORK_APPROVAL_PINS[ref]
                for ref, c in comments.items())):
        raise ValueError('network_owner_approval_not_reviewed')
    policy = auth.load_development()  # Existing trusted fixture/owner audit path.
    at = _network_utc(now)
    record = dict(schema='GS179_DEV_TEST_ONLY', owner_uid=os.getuid(),
                  approval_ref='GS-179#11916', approval_comments=comments,
                  activated_at=at.isoformat(), expires_at=(at + timedelta(seconds=DEV_NETWORK_SECONDS)).isoformat(),
                  hardware_operations_authorized=False, identity=policy['identity'])
    path = auth.DEV_STATE / 'gs179-development-11916-11917.json'
    with (auth.DEV_STATE / 'session.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            raise FileExistsError(path)
        if any(e.get('event') == 'gs179_development_authorized' for e in auth._read_private_audit(auth.DEV_MODE_AUDIT)):
            raise ValueError('development_network_already_issued_record_missing')
        sha = _network_write_once(path, record)
        _network_event('gs179_development_authorized', authorization_sha256=sha, approval_ref='GS-179#11916')
    return dict(path=str(path), sha256=sha, activated_at=record['activated_at'], expires_at=record['expires_at'])


# GS-D034: build identity is selected by reviewed image bytes, never a mode flag.
ENGINEERING_LAPTOP = 'DESKTOP-3QQU64B'
ENGINEERING_OWNER_UID = 1000
ENGINEERING_IMAGES = {
    'c3': '589dc9f98ef78fed97709e2ffb845b0a0eb6ccf5babfd9cc149743539932acb7',
    's3': 'ff1116344cbc05d4c6fcc18a8f003d067b809ef6d90236fd90bba6f86ab052e5',
}


def _engineering_build_identity():
    import gs117_hil_authorization as auth
    # Reuse the integrity-checked, audited capture, including freshness, exact
    # fixture, restoration, byte comparison and source/tool provenance checks.
    if auth.DEV_IMAGES != ENGINEERING_IMAGES:
        raise ValueError('engineering_build_allowlist_changed')
    return auth._verify_scope_a_readback_pass()


def _engineering_network_path():
    import gs117_hil_authorization as auth
    return auth.DEV_STATE / 'gs179-standing-engineering-network-v1.json'


def record_engineering_network_authorization():
    """Enroll the source-defined registered lab, without caller approval fields."""
    import os, socket, fcntl
    import gs117_hil_authorization as auth
    if auth._environment_is_release_qualified():
        raise ValueError('engineering_network_release_environment')
    if os.getuid() != ENGINEERING_OWNER_UID or socket.gethostname() != ENGINEERING_LAPTOP:
        raise ValueError('engineering_network_owner_or_laptop_mismatch')
    proof = _engineering_build_identity()
    with (auth.DEV_STATE / 'session.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        events = auth._read_private_audit(auth.DEV_MODE_AUDIT)
        if any(e.get('event') == 'gs179_engineering_authorized' for e in events):
            raise ValueError('engineering_network_already_enrolled')
        record = dict(schema='STANDING_DEV_NETWORK_ONLY_V1', approval_ref='GS-179#11947',
                      owner_uid=os.getuid(), laptop=socket.gethostname(), identity=auth.IDENTITY,
                      images=ENGINEERING_IMAGES, activated_at=_network_utc().isoformat(),
                      hardware_operations_authorized=False, build_evidence=proof)
        sha = _network_write_once(_engineering_network_path(), record)
        _network_event('gs179_engineering_authorized', authorization_sha256=sha)
    return dict(path=str(_engineering_network_path()), sha256=sha)


def _engineering_network_registration(expected_sha256, *, now=None, for_revocation=False):
    import os, socket
    from datetime import datetime
    import gs117_hil_authorization as auth
    if not for_revocation and auth._environment_is_release_qualified():
        raise ValueError('engineering_network_release_environment')
    record = _network_private_json(_engineering_network_path())
    if (auth.digest(_engineering_network_path()) != expected_sha256 or
            record.get('schema') != 'STANDING_DEV_NETWORK_ONLY_V1' or
            record.get('approval_ref') != 'GS-179#11947' or
            record.get('owner_uid') != ENGINEERING_OWNER_UID or os.getuid() != ENGINEERING_OWNER_UID or
            record.get('laptop') != ENGINEERING_LAPTOP or socket.gethostname() != ENGINEERING_LAPTOP or
            record.get('identity') != auth.IDENTITY or record.get('images') != ENGINEERING_IMAGES or
            record.get('hardware_operations_authorized') is not False):
        raise ValueError('engineering_network_registration_mismatch')
    events = auth._read_private_audit(auth.DEV_MODE_AUDIT)
    relevant = [e for e in events if e.get('authorization_sha256') == expected_sha256]
    if (any(e.get('record_sha256') != auth._canonical_record_sha256(e) for e in relevant) or
            sum(e.get('event') == 'gs179_engineering_authorized' for e in relevant) != 1):
        raise ValueError('engineering_network_audit_invalid')
    if any(e.get('event') == 'gs179_development_revoked' for e in relevant):
        raise ValueError('development_network_revoked')
    if not for_revocation and not datetime.fromisoformat(record['activated_at']) <= _network_utc(now):
        raise ValueError('engineering_network_clock_invalid')
    return dict(record, expires_at=None)


def engineering_network_authority(expected_sha256, *, now=None):
    record = _engineering_network_registration(expected_sha256, now=now)
    _engineering_build_identity()  # Every authorization use requires current proof.
    return record


def development_network_authority(expected_sha256, *, now=None):
    import os
    from datetime import datetime
    import gs117_hil_authorization as auth
    if _engineering_network_path().exists():
        _network_private_json(_engineering_network_path())
        if auth.digest(_engineering_network_path()) == expected_sha256:
            return engineering_network_authority(expected_sha256, now=now)
    if auth._environment_is_release_qualified():
        raise ValueError('development_network_release_environment')
    path = auth.DEV_STATE / 'gs179-development-11916-11917.json'
    record = _network_private_json(path)
    if auth.digest(path) != expected_sha256:
        raise ValueError('network_approval_changed')
    if (record.get('schema') != 'GS179_DEV_TEST_ONLY' or record.get('owner_uid') != os.getuid() or
            record.get('approval_ref') != 'GS-179#11916' or record.get('hardware_operations_authorized') is not False or
            set(record.get('approval_comments', {})) != set(DEV_NETWORK_APPROVAL_PINS) or
            any(c.get('author') != NETWORK_OWNER or hashlib.sha256(c.get('body', '').encode()).hexdigest() != DEV_NETWORK_APPROVAL_PINS[ref]
                for ref, c in record['approval_comments'].items())):
        raise ValueError('development_network_approval_invalid')
    events = auth._read_private_audit(auth.DEV_MODE_AUDIT)
    relevant = [e for e in events if e.get('authorization_sha256') == expected_sha256]
    if (any(e.get('record_sha256') != auth._canonical_record_sha256(e) for e in relevant) or
            sum(e.get('event') == 'gs179_development_authorized' and e.get('approval_ref') == 'GS-179#11916' for e in relevant) != 1 or
            sum(e.get('event') == 'gs179_development_authorized' for e in events) != 1):
        raise ValueError('network_approval_audit_missing')
    if any(e.get('event') == 'gs179_development_revoked' for e in relevant):
        raise ValueError('development_network_revoked')
    at = _network_utc(now)
    start, end = (datetime.fromisoformat(record[k]) for k in ('activated_at', 'expires_at'))
    if (end-start).total_seconds() != DEV_NETWORK_SECONDS or not start <= at < end:
        raise ValueError('development_network_expired_or_clock_invalid')
    return record


def revoke_development_network_authorization(expected_sha256, reason):
    import fcntl
    import gs117_hil_authorization as auth
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 240:
        raise ValueError('network_revocation_reason_required')
    with (auth.DEV_STATE / 'session.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (_engineering_network_path().exists() and
                auth.digest(_engineering_network_path()) == expected_sha256):
            _engineering_network_registration(expected_sha256, for_revocation=True)
        else:
            development_network_authority(expected_sha256)
        _network_event('gs179_development_revoked', authorization_sha256=expected_sha256, reason=reason)


def issue_development_sublease(expected_sha256, controller_pid, service_directory, *, seconds=3600, now=None,
                              predecessor_lease_id=None):
    """Prepare an immutable lease; only guarded Windows admission exposes a port.

    The Windows protected receipt remains the exclusive ACTIVE ownership record.
    Issuing a candidate cannot bypass its global non-overlap/cleanup guards.
    """
    import fcntl
    from datetime import datetime, timedelta
    import gs117_hil_authorization as auth
    if not isinstance(seconds, int) or not 1 <= seconds <= 3600:
        raise ValueError('physical_session_duration_invalid')
    with (auth.DEV_STATE / 'session.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        outer = development_network_authority(expected_sha256, now=now)
        service = _physical_service_identity(controller_pid, service_directory)
        at = _network_utc(now)
        end = at + timedelta(seconds=seconds)
        if outer['expires_at'] is not None:
            end = min(end, datetime.fromisoformat(outer['expires_at']))
        activity_at = at.isoformat()
        if predecessor_lease_id:
            development_sublease_authority(predecessor_lease_id, expected_sha256, controller_pid, service_directory, now=at)
            previous = auth.DEV_STATE / ('gs179-sublease-' + predecessor_lease_id + '.activity.json')
            activity_at = _network_private_json(previous)['at']
        sequence = 1 + sum(e.get('event') == 'gs179_sublease_issued' for e in auth._read_private_audit(auth.DEV_MODE_AUDIT))
        record = dict(authorization_sha256=expected_sha256, sequence=sequence,
                      controller_pid=controller_pid, service_directory=service_directory,
                      service=service, started=at.isoformat(), deadline=end.isoformat(), activity_origin=activity_at)
        lease_id = auth._canonical_record_sha256(record)
        record['lease_id'] = lease_id
        path = auth.DEV_STATE / ('gs179-sublease-' + lease_id + '.json')
        sha = _network_write_once(path, record)
        _network_write_once(path.with_suffix('.activity.json'), {'lease_id': lease_id, 'at': activity_at})
        _network_event('gs179_sublease_issued', authorization_sha256=expected_sha256,
                       lease_id=lease_id, lease_sha256=sha)
    return dict(lease_id=lease_id, started=record['started'], deadline=record['deadline'])


def development_sublease_authority(lease_id, expected_sha256, controller_pid, service_directory, *, now=None):
    import re
    from datetime import datetime, timedelta
    import gs117_hil_authorization as auth
    outer = development_network_authority(expected_sha256, now=now)
    if not re.fullmatch('[a-f0-9]{64}', lease_id or ''):
        raise ValueError('network_lease_id_invalid')
    path = auth.DEV_STATE / ('gs179-sublease-' + lease_id + '.json')
    record = _network_private_json(path)
    base = dict(record); base.pop('lease_id', None)
    issued = [e for e in auth._read_private_audit(auth.DEV_MODE_AUDIT) if
              e.get('event') == 'gs179_sublease_issued' and e.get('lease_id') == lease_id]
    if (auth._canonical_record_sha256(base) != lease_id or len(issued) != 1 or
            issued[0].get('record_sha256') != auth._canonical_record_sha256(issued[0]) or
            issued[0].get('lease_sha256') != auth.digest(path) or
            record.get('authorization_sha256') != expected_sha256 or
            record.get('controller_pid') != controller_pid or record.get('service_directory') != service_directory):
        raise ValueError('network_sublease_binding_invalid')
    at = _network_utc(now)
    start, end = (datetime.fromisoformat(record[k]) for k in ('started', 'deadline'))
    activity = _network_private_json(path.with_suffix('.activity.json'))
    last = datetime.fromisoformat(activity['at'])
    if (activity.get('lease_id') != lease_id or not start <= at < end or
            not datetime.fromisoformat(record['activity_origin']) <= last <= at or
            not 0 < (end-start).total_seconds() <= 3600 or
            (outer['expires_at'] is not None and end > datetime.fromisoformat(outer['expires_at'])) or (at-last).total_seconds() >= NETWORK_IDLE_SECONDS):
        raise ValueError('network_sublease_expired_or_idle')
    service = _physical_service_identity(controller_pid, service_directory)
    if service != record['service']:
        raise ValueError('network_sublease_service_identity_changed')
    return dict(scope_id=lease_id, activation=expected_sha256, **service,
                lease_started=record['started'], lease_deadline=record['deadline'],
                activity_deadline=(last + timedelta(seconds=NETWORK_IDLE_SECONDS)).isoformat(),
                outer_deadline=outer['expires_at'] or record['deadline'],
                standing_authority=outer['expires_at'] is None, hardware_operations_authorized=False)


def note_development_activity(lease_id, expected_sha256, controller_pid, service_directory, *, now=None):
    """Explicit work only; polling/ticks NEVER manufacture development activity."""
    import fcntl
    import gs117_hil_authorization as auth
    with (auth.DEV_STATE / 'session.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        development_sublease_authority(lease_id, expected_sha256, controller_pid, service_directory, now=now)
        path = auth.DEV_STATE / ('gs179-sublease-' + lease_id + '.activity.json')
        auth._atomic_private_json(path, dict(lease_id=lease_id, at=_network_utc(now).isoformat()))
        _network_event('gs179_development_activity', authorization_sha256=expected_sha256,
                       lease_id=lease_id, controller_pid=controller_pid)


def _network_private_json(path):
    import os, stat, json
    path = Path(path)
    info = path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(info.st_mode) or
            info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise ValueError('network_approval_not_private')
    return json.loads(path.read_text())


def _network_approval_path():
    import gs117_hil_authorization as auth
    return auth.DEV_STATE / 'gs179-network-11910-11911.json'


def record_network_window_approval(comments):
    """Record reviewed owner snapshots once through the EXISTING private audit.

    No hardware activation, policy update, session reservation or renewal.
    A source-reviewed grant cannot be reissued with different hardware binding.
    """
    import json, os, fcntl
    from datetime import datetime, timezone
    import gs117_hil_authorization as auth
    if (set(comments) != set(NETWORK_APPROVAL_PINS) or
            any(c.get('author') != NETWORK_OWNER or
                hashlib.sha256(c.get('body', '').encode()).hexdigest() != NETWORK_APPROVAL_PINS[ref]
                for ref, c in comments.items())):
        raise ValueError('network_owner_approval_not_reviewed')
    policy = auth.load_development()
    status = auth.development_status()
    if (status['status'] != 'ACTIVE' or status['sessions'] != 0 or
            status['session_limit'] != 1 or policy['owner_approval_ref'] != 'GS-117#11897'):
        raise ValueError('network_hardware_binding_invalid')
    record = dict(schema='GS179_NETWORK_WINDOWS_V1', owner_uid=os.getuid(),
                  approval_ref='GS-117#11910', approval_comments=comments,
                  hardware_scope=status['authorization_scope_id'],
                  hardware_activation=policy['development_mode']['activation_id'],
                  hardware_policy_sha256=auth.digest(auth.DEV_POLICY),
                  windows={'A': {'purpose': 'NETWORK_ONLY', 'max_seconds': 3600},
                           'B': {'purpose': 'EXISTING_OBSERVATION_ONLY', 'max_seconds': 3600}})
    path = _network_approval_path()
    # Same audit lock and private/O_NOFOLLOW file rules as existing authority.
    with (auth.DEV_STATE / 'session.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        raw = (json.dumps(record, sort_keys=True) + '\n').encode()
        sha = hashlib.sha256(raw).hexdigest()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(raw); out.flush(); os.fsync(out.fileno())
        event = dict(event='gs179_network_approval_reviewed', at_utc=datetime.now(timezone.utc).isoformat(),
                     network_approval_sha256=sha, hardware_scope=record['hardware_scope'],
                     hardware_activation=record['hardware_activation'])
        event['record_sha256'] = auth._canonical_record_sha256(event)
        auth._append_private_audit(auth.DEV_MODE_AUDIT, event)
    return {'path': str(path), 'sha256': sha}


def _network_window_binding(window, expected_sha256, policy, status):
    import os, re
    import gs117_hil_authorization as auth
    path = _network_approval_path()
    if window not in ('A', 'B') or not re.fullmatch('[a-f0-9]{64}', expected_sha256 or ''):
        raise ValueError('network_window_input_invalid')
    record = _network_private_json(path)
    if auth.digest(path) != expected_sha256:
        raise ValueError('network_approval_changed')
    if (record.get('schema') != 'GS179_NETWORK_WINDOWS_V1' or record.get('owner_uid') != os.getuid() or
            record.get('approval_ref') != 'GS-117#11910' or
            set(record.get('approval_comments', {})) != set(NETWORK_APPROVAL_PINS) or
            any(c.get('author') != NETWORK_OWNER or
                hashlib.sha256(c.get('body', '').encode()).hexdigest() != NETWORK_APPROVAL_PINS[ref]
                for ref, c in record['approval_comments'].items()) or
            record.get('windows') != {'A': {'purpose': 'NETWORK_ONLY', 'max_seconds': 3600},
                                     'B': {'purpose': 'EXISTING_OBSERVATION_ONLY', 'max_seconds': 3600}} or
            record.get('hardware_policy_sha256') != auth.digest(auth.DEV_POLICY) or
            record.get('hardware_scope') != status['authorization_scope_id'] or
            record.get('hardware_activation') != policy['development_mode']['activation_id']):
        raise ValueError('network_approval_binding_mismatch')
    events = auth._read_private_audit(auth.DEV_MODE_AUDIT)
    matching = [e for e in events if e.get('event') == 'gs179_network_approval_reviewed' and
                e.get('network_approval_sha256') == expected_sha256]
    if (len(matching) != 1 or matching[0].get('record_sha256') != auth._canonical_record_sha256(matching[0]) or
            matching[0].get('hardware_scope') != record['hardware_scope'] or
            matching[0].get('hardware_activation') != record['hardware_activation']):
        raise ValueError('network_approval_audit_missing')
    for e in events:
        if (e.get('event') == 'gs179_network_window_revoked' and
                e.get('network_approval_sha256') == expected_sha256 and e.get('window') == window):
            raise ValueError('network_window_revoked')
    return dict(scope_id=hashlib.sha256((expected_sha256 + ':' + window).encode()).hexdigest(),
                activation=expected_sha256, network_window=window, network_approval_sha256=expected_sha256,
                hardware_scope=record['hardware_scope'], hardware_activation=record['hardware_activation'],
                hardware_operations_authorized=False)


def revoke_network_window(window, expected_sha256, reason):
    """Append network-only revocation; never touch the hardware policy/ledger."""
    import fcntl
    from datetime import datetime, timezone
    import gs117_hil_authorization as auth
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 240:
        raise ValueError('network_revocation_reason_required')
    with (auth.DEV_STATE / 'session.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _network_window_binding(window, expected_sha256, auth.load_development(), auth.development_status())
        event = dict(event='gs179_network_window_revoked', window=window,
                     network_approval_sha256=expected_sha256, reason=reason,
                     at_utc=datetime.now(timezone.utc).isoformat())
        event['record_sha256'] = auth._canonical_record_sha256(event)
        auth._append_private_audit(auth.DEV_MODE_AUDIT, event)



def _physical_service_identity(controller_pid, service_directory):
    import os
    private_json = _network_private_json
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
    return dict(controller_start=controller_start, wsl_address=wsl_ipv4(), service_pid=process['pid'],
                service_start=ingress_proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19],
                service_sha256=process['sha256'])

def physical_ingress_authority(approval_ref, controller_pid, service_directory,
                               network_window='', network_approval_sha256='', network_lease_id=''):
    """Read existing DEV authority and bounded launcher receipts; never reserve it.

    This is a projection for the Windows network utility, not hardware consent.
    A network session cannot renew the DEV scope or start/restart its services.
    """
    import json
    import os
    import stat
    import gs117_hil_authorization as auth

    if network_window == 'DEV':
        if approval_ref not in {'GS-179#11916', 'GS-179#11947'}:
            raise ValueError('development_network_reference_invalid')
        if development_network_authority(network_approval_sha256)['approval_ref'] != approval_ref:
            raise ValueError('development_network_reference_invalid')
        return {'approval_ref': approval_ref, **development_sublease_authority(
            network_lease_id, network_approval_sha256, controller_pid, service_directory)}
    if network_lease_id:
        raise ValueError('network_lease_id_not_applicable')

    def private_json(path):
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_mode & 0o077):
            raise ValueError("physical_session_receipt_not_private")
        return json.loads(path.read_text())

    policy = auth.load_development()
    if ((policy['owner_approval_ref'] != approval_ref if not network_window else approval_ref != 'GS-117#11910') or
            policy['procedures'] != ['protected_gs40_bootstrap'] or
            policy.get('max_sessions') != 1 or policy.get('max_retries') != 0 or
            policy.get('observation_seconds') != 90 or
            policy.get('max_bootstraps_per_session') != 1 or
            policy.get('motion_injection_authorized') is not False):
        raise ValueError('physical_session_authorization_scope_mismatch')
    status = auth.development_status()
    network = (_network_window_binding(network_window, network_approval_sha256, policy, status)
               if network_window else None)
    if network_window == 'A' and status['status'] != 'ACTIVE':
        raise ValueError('network_qualification_hardware_not_idle')
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
    return {'approval_ref': approval_ref, 'scope_id': status['authorization_scope_id'],
            'activation': policy['development_mode']['activation_id'],
            **_physical_service_identity(controller_pid, service_directory), **(network or {})}


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--physical-ingress-authority', required=True)
    parser.add_argument('--controller-pid', required=True, type=int)
    parser.add_argument('--service-directory', required=True)
    parser.add_argument('--network-window', default='', choices=('', 'A', 'B', 'DEV'))
    parser.add_argument('--network-approval-sha256', default='')
    parser.add_argument('--network-lease-id', default='')
    parser.add_argument('--issue-development-sublease', action='store_true')
    args = parser.parse_args()
    try:
        if args.issue_development_sublease:
            if args.physical_ingress_authority != 'GS-179#11916' or args.network_window != 'DEV':
                raise ValueError('development_network_reference_invalid')
            value = issue_development_sublease(args.network_approval_sha256, args.controller_pid,
                args.service_directory, predecessor_lease_id=args.network_lease_id)
        else:
            value = physical_ingress_authority(args.physical_ingress_authority, args.controller_pid,
                args.service_directory, args.network_window, args.network_approval_sha256, args.network_lease_id)
        print(json.dumps(value))
    except Exception as error:
        print(json.dumps({'error': type(error).__name__}))
        raise SystemExit(2)
