# GS-168 TEST_ONLY credential issuer

Standalone software simulation: `pilot_test_issuer.py` (Python 3, `cryptography`, SQLite). It is **not** an ESP32 key injector, manufacturing CA, production CloudSync verifier or customer-device certificate authority. This code does not contact hardware, the backend or the network.

From `code/`:

~~~python
from tools.factory.pilot_test_issuer import TestOnlyIssuer, new_test_csr

issuer = TestOnlyIssuer(":memory:", environment="TEST_ONLY")
fixture_private_key, fixture_csr = new_test_csr("test-hub-001")
credential = issuer.issue("test-hub-001", fixture_csr)
issuer.verify(credential.certificate_pem, "test-hub-001", expected_csr=fixture_csr)
issuer.revoke(credential.fingerprint)
issuer.close()
~~~

The host-only fixture private key above is synthetic and must never be logged or exported. It is not a device-protected S3 DS key. The ephemeral test CA private key remains in process memory; SQLite contains **only public certificates and issuance status**. A separate instance can reopen metadata only when retaining the same in-memory test CA object. Real-process restart without that ephemeral CA intentionally refuses the prior DB; protected real-CA custody/backup belongs to GS-172.

Focused test command:

~~~bash
python3 -m unittest discover -s code/tests/python -p 'test_gs168_pilot_issuer.py' -v
~~~

Optional slower 100-unit sequential synthetic batch:

~~~bash
GS168_TEST_100=1 python3 -m unittest discover -s code/tests/python -p 'test_gs168_pilot_issuer.py' -v
~~~

**Safety boundary:** TEST_ONLY root and leaves carry a critical proprietary marker, and non-TEST_ONLY mode throws `NOT_READY_SECURITY_APPROVAL`. Real customer infrastructure must exclude all test CA roots and credentials, regardless of certificate contents. No real device provisioning, USB/serial, eFuse changes, firmware flashing, production CloudSync or manufacturing READY claims are authorized.

GS-166 documents the minimal contract. GS-167, GS-169, GS-170 and GS-171 own future station CLI, QR registry, QA and wider integration tests. GS-172 independently gates the real hardware/credential procedure.
