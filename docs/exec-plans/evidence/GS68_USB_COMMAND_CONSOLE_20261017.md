# GS-68 USB command-console correction — 2026-10-17

## Scope and disposition

This receipt follows GS-172 comment 11323 and GS-68 comment 11324. The work is
limited to the isolated `GS68_CLOUDSYNC_DS_MTLS_HIL` ESP32-S3 TEST_ONLY
diagnostic. Production sdkconfig defaults, product composition, `UnprovisionedS3CloudTrust`,
certificate checks, signed-time cryptography, and physical evidence were left
unchanged.

Canonical branch: `feature/r1-commercial-baseline`. Diagnostic source commit:
`a5d2806b40023d0c42a90d082187398416fb956c`. Code tree OID:
`c5dccea2fd0e1fd3f8d93e608502237f52019717`.

## Finding and correction

The previous candidate's effective sdkconfig selected
`CONFIG_ESP_CONSOLE_UART_DEFAULT=y` and
`CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y`, while the spare S3's command
host uses native USB Serial/JTAG. ESP-IDF 6.0.3 documents that the secondary
console is output-only. Its default simplified USB VFS read returns only bytes
currently present and is nonblocking, so the previous `fgets()` loop could miss
stdin or leave `app_main` when input was delayed or partial.

The diagnostic profile now selects USB Serial/JTAG as the primary console and
explicitly disables UART0 primary and secondary USB console selection. The
diagnostic installs the USB Serial/JTAG driver, switches the VFS to its
driver-backed path, clears `O_NONBLOCK` on stdin, and leaves stdin unbuffered.
The command loop uses a bounded incremental frame accumulator and never exits
on an empty/error read: it clears stdio's error, waits briefly, and retries.
CR, LF, and CRLF delimiters work; a partial command remains buffered; invalid,
NUL-containing, and oversized input is rejected through its line boundary so
the following command remains aligned. The existing 1024-byte command limit,
case/nonce validation, RSA-3072/SHA-256 proof verification, and fail-closed
identity/TLS behavior are preserved.

Configuration is guarded in three places: the TEST_ONLY profile, compile-time
diagnostic assertions, and the build helper's generated-sdkconfig validation.
The helper also reports USB primary and blocking stdin in its build receipt.
The test extends the existing GS-116/GS-130 registered diagnostic stage; it
adds no validation framework or physical test ID.

## Validation

| Check | Result |
|---|---|
| `make -C code gs68-node-diag-protocol-host-test` | PASS — 1,736 parser/framing assertions, including delayed split input, invalid input recovery, CR/LF/CRLF, sequential commands, NUL rejection, and oversized-line draining |
| `make -C code cloud-trust-provider-test` | PASS — 5 provider suites: D05 authority, D12 credential, D06 state machine and signed-proof crypto, and GS-40 provider/CloudSync integration |
| `make -C code cloudsync-security-ut` | PASS — mTLS adapter 9/9; backend security 14/14; GS-40 identity/time/caregiver 4/4; GS-168 issuer/registry 10/10; NodeHealth 5/5 |
| `make -C code gs130-hil-runner-test` | PASS — 72 tests; physical runner defaults remained NOT_RUN/BLOCKED and opened no port |
| ESP-IDF 6.0.3 non-flashing S3 diagnostic build | PASS — build-only, no serial or hardware action |

The first build attempt reached link but `/tmp` was a full 1.9 GiB tmpfs. The
failed logs and artifacts were preserved. The same build completed from the
ignored `code/build/validation_targets` area with compiler `TMPDIR` pointed to
that area; the root filesystem had ample free capacity. This did not change
source, sdkconfig, or image bytes.

## Source and image receipt

| Item | Value |
|---|---|
| ESP-IDF | `v6.0.3` |
| Target/profile | ESP32-S3, `GS68_CLOUDSYNC_DS_MTLS_HIL`, TEST_ONLY |
| Profile SHA-256 | `7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72` |
| Effective sdkconfig SHA-256 | `ff3150eeeac79a4a80b5a718a20408386d90d5a491cb199d763e0b6190105a7a` |
| Effective primary console | USB Serial/JTAG (`CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`) |
| UART0 primary / USB secondary | Disabled / disabled |
| stdin mode | USB driver-backed blocking read; unbuffered stdio |
| Image size | 473,312 bytes |
| New build-only image SHA-256 | `c0fb82c69fe030f8a4358b7783e7c537156dfdb361b4df1a620831210d1bef65` |
| Build report | `code/build/validation_targets/gs68_cloudsync_diag_20261017_usb_console/gs68_build_report.json` (ignored local artifact) |

**Supersession:** the earlier build-only candidate
`e8e0a6236817f857346aced735f94f412245c693733710f749d56a55b248ef34` is
superseded for any future installation by the USB-console candidate above.
The user-reported installed spare-S3 baseline
`c905af73419c84af7a1d986dada3724da7e654b4d7eaa0235bd06e515902f8ef` is
unchanged. The new candidate was not installed, and the prior build-only image
was not installed either.

## Next separately authorized installation

**Assessment: READY FOR OWNER REVIEW AND SEPARATE INSTALLATION AUTHORIZATION;
NOT physically validated.** This is a source-matched build candidate, not an
authorization to access, flash, reset, or test the spare S3. Before installation,
the owner must authorize the exact spare fixture, this image digest, the
installation method, operator, evidence location, and recovery/stop plan.
Existing GS-114/C8 assets remain excluded.

After a separate approval and installation, first match the running-image
digest to the value above. Before PSA RNG or signed-time cases, perform a
read-only console smoke check on the approved stable USB identity: wait after
startup; send one harmless `OBSERVE` command in two delayed fragments with
CRLF; send malformed input followed by a valid command; then send two harmless
commands sequentially. Verify the expected response for each, no app exit/reset,
and no unexpected network attempt. A console mismatch or missing response is
STOP/FAIL and leaves the crypto cases NOT_RUN.

Even after that smoke check, actual USB receive behavior, PSA RNG, target RSA
verification, DS signing, mTLS, and current-image identity remain NOT_RUN until
the corresponding approved physical observations pass. The image has no
provisioned DS/HMAC context, production certificate, production time anchor,
or commercial endpoint. GS-68 and GS-40 physical acceptance remain NOT_RUN.
