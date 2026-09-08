# Ghar Sajag hardware-independent reference implementation v1.1

This repository is the executable engineering baseline paired with the Ghar Sajag P0 requirements. It implements the deterministic and host-testable parts of all 32 logical modules while keeping hardware drivers behind explicit ports.

## Diagnostics

Production ERROR logging is enabled by default; development call-flow TRACE is build-gated. Host/backend logs are bounded `.txt` files, while the browser uses a 128-record ring with text export. See `docs/LOGGING_DESIGN.md`.

```bash
make verify          # production profile
make verify-trace    # development call-flow profile
make verify-sanitize # memory/undefined-behaviour checks
make simulate-matrix # four compile-time feature-flag scenarios
```

Feature defaults and safe P1/P2 gates are documented in `docs/FEATURE_FLAGS.md`.

## What is implemented

- Versioned node, cloud and configuration contracts (S01).
- Pure routine, coverage and incident decisions in C++ (S02).
- Host implementations of N01-N05 and H01-H08, including bounded queues, retry, deduplication, local rule evaluation and cloud-outbox semantics.
- Security/update policy interfaces and a host verifier seam (S03). Production cryptographic verification is intentionally not faked.
- In-memory Python services for B01-B08 with tenant authorization, consent, idempotent ingest, incident ownership, backup routing, configuration versions, projections and audit.
- Framework-neutral browser-domain modules for A01-A05, tested with Node.js.
- Simulation/CI assets (T01), safe HIL command scaffolding (T02) and pilot deployment/runbook examples (T03).

## What still requires boards or selected vendors

ESP32 GPIO/wake behavior, ESP-NOW encryption/channel recovery, NVS/flash partitions, ADC calibration, current draw, buttons/display/audio, Wi-Fi/MQTT/TLS, secure-element/NVS credential storage, signed OTA and power-path behavior. The code marks these as adapters or qualification gates.

## Run the host verification

```sh
make verify
```

This builds the portable C++ tests and simulator with `g++`, runs Python `unittest`, validates JSON contracts and runs the app-domain tests with Node.js. No network service or physical hardware is required.

## Module identifiers

`N` = node firmware, `H` = hub firmware, `B` = backend, `A` = caregiver app, `S` = shared, and `T` = test/operations. A requirement can name several modules because it crosses boundaries; that does not turn the modules into separate services.

See `IMPLEMENTATION_STATUS.md` for the exact completion boundary and the accompanying low-level design for code flow and interfaces.
