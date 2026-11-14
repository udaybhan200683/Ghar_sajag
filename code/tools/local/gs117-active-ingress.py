from pathlib import Path
import hashlib
import sys, os, shlex, json, time, signal, threading, base64
from datetime import datetime, timezone, timedelta
ROOT = Path('/home/udaybhan/projects/Ghar_sajag_r1')
sys.path[:0] = [str(ROOT / 'code/backend'), str(ROOT / 'code/tools/hil'), str(ROOT / 'code/tools/factory')]
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from ghar_sajag.gs179_hub_ingress_runtime import HubIngressRuntimeConfig, start_gs179_test_only_hub_ingress
from ghar_sajag.cloud_client_identity import TimeReadiness
from pilot_test_issuer import TestOnlyAuthority, TestOnlyIssuer
from gs40_test_bootstrap import AuthorityService
from gs68_signed_time_fixture import TestOnlySignedTimeFixture
os.umask(63)
state = Path(os.environ['GS117_SERVICE_DIRECTORY'])
trust = Path.home() / '.config/ghar-sajag/gs117-tc001'
service = Path.home() / '.local/share/ghar-sajag/gs179-laptop'

def load(name):
    return serialization.load_pem_private_key((trust / name).read_bytes(), password=None)

class SignedFixtureTime:

    def __init__(self):
        self.key = load('physical-time-signing-private.pem')
        self.fixture = TestOnlySignedTimeFixture(private_key=self.key)
        self.at = -1000.0
        self.lock = threading.RLock()

    def current_utc(self):
        with self.lock:
            elapsed = time.monotonic() - self.at
            if elapsed >= 60:
                proof = base64.b64decode(self.fixture.proof_command({'schema': 'gs68.target.event.v1', 'event': 'time_challenge', 'case_id': 'GS68-AUX-TIME-001', 'boot_generation': 1, 'challenge_nonce': os.urandom(32).hex()})['payload_b64'])
                self.key.public_key().verify(proof[72:], proof[:72], padding.PKCS1v15(), hashes.SHA256())
                self.utc = datetime.fromtimestamp(int.from_bytes(proof[48:56], 'big'), timezone.utc)
                self.at = time.monotonic()
                elapsed = 0
            return self.utc + timedelta(seconds=elapsed)

    def readiness(self):
        self.current_utc()
        return TimeReadiness.TRUSTED
trusted = SignedFixtureTime()
cfg = {}
for raw in (Path.home() / '.config/ghar-sajag/gs179-laptop/server.env').read_text().splitlines():
    if raw.startswith('export ') and '=' in raw:
        k, v = raw[7:].split('=', 1)
        cfg[k] = shlex.split(v)[0]
import subprocess
bind = subprocess.check_output(['ip', '-4', '-o', 'addr', 'show', 'dev', 'eth0'], text=True).split('inet ')[1].split('/')[0]
issuer = TestOnlyIssuer(trust / 'physical-issuer.sqlite3', authority=TestOnlyAuthority.for_gs117_fixture(trust / 'physical-test-ca.pem', initialize=False))
config = HubIngressRuntimeConfig(enabled=True, profile='GS179_TEST_ONLY', dsn=cfg['GS179_LOCAL_SERVER_DSN'], server_cert=service / 'tls/android/server.pem', server_key=service / 'tls/android/server.key', client_ca=trust / 'physical-client-ca.pem', hub_id='hub-e072a1d38d34', home_id='gs177-test-product', installation_epoch=1, bind_host=bind, port=8445, allow_private_bind=True)
trace = state / 'real-hub-ingress-trace.jsonl'
import importlib.util
configuration_template_path = Path('/home/udaybhan/.local/state/ghar-sajag/gs117-tc001/standing-readiness-prepared/gs117-protected-bootstrap-development-v25.py')
if hashlib.sha256(configuration_template_path.read_bytes()).hexdigest() != '7fef648b2b1e06a935fe24415d560412272aaf376f932d183c09630a71d54377':
    raise ValueError('REVIEWED_RUNTIME_TEMPLATE_CHANGED')
spec = importlib.util.spec_from_file_location('gs117_runtime_template', configuration_template_path)
template = importlib.util.module_from_spec(spec)
spec.loader.exec_module(template)
configuration_fields = template.runtime_configuration_fields()
holder = {}
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())

def result(route, request, status, response):
    row = {'at': datetime.now(timezone.utc).isoformat(), 'route': route, 'http_status': status, 'receipt_status': response.get('status') if isinstance(response, dict) else None, 'duplicate': response.get('duplicate') if isinstance(response, dict) else None, 'event_key': request.get('event_key') if isinstance(request, dict) else None, 'receipt_event_key': response.get('event_key') if isinstance(response, dict) else None}
    with trace.open('a') as f:
        f.write(json.dumps(row) + '\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(row), flush=True)
runtime = start_gs179_test_only_hub_ingress(config, credentials=issuer, trusted_time=trusted, authority_refresh=lambda peer, body: holder['authority'].refresh(peer, body), on_result=result)
holder['authority'] = AuthorityService(issuer, runtime.durable_api.db, runtime.durable_api.api.service.lock, clock=lambda: trusted.current_utc().timestamp(), enabled=True, signer=load('physical-authority-signing-private.pem'), configuration_fields=configuration_fields, configuration_signer=load('config-root-private.pem'), configuration_home_id='gs177-test-product')
try:
    print(json.dumps({'event': 'READY', 'pid': os.getpid(), 'status': runtime.status(), 'time_source': 'EXPLICIT_OWNER_APPROVED_SIGNED_GS68_TEST_ONLY_AUTHORITY'}), flush=True)
    while not stop.wait(2):
        (state / 'ingress-runtime-status.json').write_text(json.dumps({'pid': os.getpid(), 'at': datetime.now(timezone.utc).isoformat(), 'status': runtime.status()}))
finally:
    runtime.close()
    issuer.close()
    print('GS117_BOUNDED_INGRESS_STOPPED', flush=True)
