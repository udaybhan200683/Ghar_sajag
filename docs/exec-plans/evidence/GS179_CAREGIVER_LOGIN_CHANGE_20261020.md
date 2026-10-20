# GS-179 caregiver login change — 2026-10-20

## Scope and result

Implemented the owner-requested self-service command
`code/tools/local/gs179-laptop-server.sh change-login` for the existing
laptop-hosted GS-179 TEST_ONLY caregiver account. The feature changes the
existing account row; it does not create an account or change the account ID,
Home membership, role, ownership epoch, committed events, caregiver history or
monitoring data. The live laptop account was not changed during implementation
or testing.

The command obtains the email with ordinary interactive input and obtains the
password twice through hidden `getpass` prompts. It requires a controlling TTY,
normalizes and validates the email, requires an exact confirmation and applies
the existing GS-177 Scrypt password hash and its 16–256 character bounds. It
verifies the owner-only TEST_ONLY credential file, current credential against
the active database account, and active matching TEST_ONLY Home membership and
ownership epoch before it proceeds. It rejects an email already owned by a
different account.

The database email/hash update and revocation of all active sessions share one
database transaction. A private mode-0600 pending envelope is fsynced before
that transaction; after commit, the credential JSON is atomically replaced and
the containing directory is fsynced. A subsequent invocation reconciles a
pending envelope against the exact target password hash and account/Home. If
the DB commit happened, it finalizes the JSON and exits; if the DB remains
bound to the old private credential, it safely discards the uncommitted pending
state and continues. Ambiguous recovery state fails closed and is preserved for
inspection. The credential JSON remains in the existing mode-0700 private
state directory and is never printed or written to Git/Jira.

The existing health-source and caregiver browser helpers continue reading the
same `caregiver-login.json` fields; the update preserves existing keys and adds
the stable account ID for stronger subsequent binding. An atomic rename means
concurrent readers see either a complete old file or a complete new file.

## Changes

- `code/tools/local/gs179-laptop-server.sh` — adds the `change-login` command.
- `code/tools/local/gs179_change_login.py` — private interactive flow, account
  binding, transactional update, session revocation and interrupted-update
  recovery.
- `code/parivar_saathi_android_app/server/tests/test_connected_lite.py` — five
  focused tests, including run against SQLite and opt-in isolated PostgreSQL.
- `code/validation/suites.json` — registers helper and PostgreSQL test support
  as inputs to the existing connected caregiver suite.

No new credentials, real identity material, production policy, API or database
schema was introduced.

## Validation

Executed against current source on `feature/r1-commercial-baseline`:

| Command | Result |
|---|---|
| `python3 -m unittest discover -s parivar_saathi_android_app/server/tests -p test_connected_lite.py -k CaregiverLoginChangeTests -v` | PASS, 5/5; SQLite test database |
| Same focused command with `GS179_CHANGE_LOGIN_TEST_DSN` set from the owner-only laptop service config | PASS, 5/5; each test used and dropped a fresh isolated schema in local TLS PostgreSQL |
| `python3 validation/run_gs177_connected_lite.py` | PASS, registered stage: API 20/20, caregiver runtime 8/8, lab build PASS, 3/3 registered host scenarios PASS, physical `NOT_RUN`; exit 0 |
| `python3 -m py_compile tools/local/gs179_change_login.py parivar_saathi_android_app/server/tests/test_connected_lite.py` | PASS |
| `bash -n tools/local/gs179-laptop-server.sh` | PASS |
| `python3 -m json.tool validation/suites.json` | PASS |
| `git diff --check` | PASS |

The PostgreSQL test used the existing local server's TLS-verified DSN but did
not target its application schema: the fixture created isolated random schemas,
verified account/password/session and data-preservation behavior there, and
dropped those schemas on successful cleanup. Four incomplete test schemas left
by an earlier failed fixture setup in this run were identified by their exact
TEST_ONLY fixture contents and removed; they contained only test account/Home
and schema rows, with no event/monitoring or caregiver-history rows. No
public/live application schema rows were modified. No test printed or persisted
a test password outside its owner-only temporary directory.

Test harness corrections encountered before final PASS: the first PostgreSQL
attempt needed the bundled libpq directory in `LD_LIBRARY_PATH`; the next
exposed raw SQLite-style placeholders in the new cross-dialect fixture. The
fixture was corrected to use `Store.sql`, and cleanup now runs even when setup
fails. The first combined PostgreSQL-plus-registered-suite invocation also
carried the laptop's opt-in LAN profile into public-origin tests; rerunning the
registered stage with those local-only variables unset passed. These were test
setup issues, not changes to login behavior.

The successful path verifies preserved Hub/Home-bound identity, role, epoch,
caregiver run/history and a durable EventKey commit; old session rejection and
old-password login failure; new-password login success; duplicate email and
invalid/mismatched input rejection; and recovery after a simulated process stop
between DB commit and credential-file promotion. This is software validation,
not phone or physical Hub qualification.

## Remaining status

GS-179 remains In Progress. No product/security decision is needed for this
local TEST_ONLY account maintenance operation. The operator should run the
command from the canonical WSL checkout while attached to an interactive
terminal. The current laptop account and monitoring data remain unchanged
until the owner enters the new login privately.
