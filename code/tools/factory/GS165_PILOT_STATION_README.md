# GS-165 Pilot Station v1 (simulation only)

This local Python CLI is for one operator and sequential synthetic work. It does
not discover boards, open USB/serial, flash firmware, write eFuses, create real
credentials, contact production services, assign a Home, or qualify a device for
delivery. Every station result says `SIMULATED`; physical QA stays `NOT_RUN` and
delivery readiness stays `NOT_READY_SIMULATION_ONLY`.

Run from `code/`. Use a new station database for a new isolated simulation or
batch. The GS-168 issuer database stores only public certificate data and metadata; its
TEST_ONLY CA key is held in process memory and is not backed up. Reopening both
databases requires the same in-memory TEST_ONLY authority. If that authority is
lost, the issuer refuses its old database. Do not bypass the refusal; preserve
the files for review and begin a separately identified synthetic run. After a
process restart, `verify` and `export-public` read the public registry and mark
that certificate-chain validation was not repeated because the ephemeral issuer
key is unavailable. `resume` returns a completed matching record idempotently;
an incomplete record fails closed as `NOT_READY_TEST_ISSUER_AUTHORITY_LOST`.

```bash
python3 tools/factory/pilot_station.py --registry /tmp/gs165-pilot.sqlite3 \
  simulate-one test-hub-001 --source-version git-commit \
  --firmware-version synthetic-build-1 \
  --firmware-sha256 <64-lowercase-hex> --source-head <source-revision> \
  --artifact-sha256 <64-lowercase-hex>

python3 tools/factory/pilot_station.py --registry /tmp/gs165-batch.sqlite3 \
  simulate-batch --count 100 --source-version git-commit \
  --firmware-version synthetic-build-1 \
  --firmware-sha256 <64-lowercase-hex> --source-head <source-revision> \
  --artifact-sha256 <64-lowercase-hex>

python3 tools/factory/pilot_station.py --registry /tmp/gs165-pilot.sqlite3 \
  verify test-hub-001
python3 tools/factory/pilot_station.py --registry /tmp/gs165-pilot.sqlite3 \
  resume test-hub-001 --source-version git-commit \
  --firmware-version synthetic-build-1 \
  --firmware-sha256 <64-lowercase-hex> --source-head <source-revision> \
  --artifact-sha256 <64-lowercase-hex>
python3 tools/factory/pilot_station.py --registry /tmp/gs165-pilot.sqlite3 \
  quarantine test-hub-001 --reason operator_review_retryable
python3 tools/factory/pilot_station.py --registry /tmp/gs165-pilot.sqlite3 \
  recover test-hub-001 --confirm 'RECOVER test-hub-001' \
  --source-version git-commit --firmware-version synthetic-build-1 \
  --firmware-sha256 <64-lowercase-hex> --source-head <source-revision> \
  --artifact-sha256 <64-lowercase-hex>
python3 tools/factory/pilot_station.py --registry /tmp/gs165-pilot.sqlite3 export-public
```

The SQLite registry has unique permanent Hub ID, certificate fingerprint and QR
handle constraints. It records issuer reference, source/artifact provenance,
state, simulated QA and a reason-coded audit trail. It has no Home, installation
epoch, Node identity or private-key fields. QR values are random public lookup
references and grant no authority. Conflicting identity/provenance is
quarantined. Provenance labels accept bounded safe tokens and content hashes;
quarantine reasons cannot be changed to bypass recovery rules. Recovery requires
the exact Hub ID confirmation and cannot recover an identity conflict. Batch
size is limited to 1–100 and processed sequentially.

Allowed states are `NEW -> RESERVED -> TEST_CREDENTIAL_ISSUED ->
SIMULATED_QA_PASS`; failures may enter `QUARANTINED`. A quarantined record can
return to `RESERVED` only through explicit recovery review. There is no
`READY_FOR_DELIVERY` state. Interrupted registry transactions roll back; retry
can reuse the already issued public TEST_ONLY certificate while the same
in-memory issuer authority remains available. A process restart can read
completed results but cannot resume issuance or a partial unit after losing that
authority. This fails closed as required by GS-166/GS-168.

Export JSON is public and sanitized. It contains fingerprints and opaque public
QR identifiers, but no certificate PEM, CSR, private key, token, Home identity,
or Node credential. Back up the station SQLite database as a consistent SQLite
backup (not by copying only the live database file while WAL writes are active):

```bash
python3 -c 'import sqlite3; src=sqlite3.connect("pilot-station.sqlite3"); dst=sqlite3.connect("pilot-station-backup.sqlite3"); src.backup(dst); dst.close(); src.close()'
```

The backup does not preserve the in-memory TEST_ONLY CA key. It remains useful
for sanitized reports, but it cannot resume incomplete issuance.

Focused deterministic registration (also reruns the prior GS-168 issuer tests):

```bash
cd code
python3 -m unittest discover -s tests/python -p 'test_gs16*_pilot*.py' -v
```

This host simulation is not an S3 hardware acceptance, a production security
approval, or authorization for a physical provisioning operation.
