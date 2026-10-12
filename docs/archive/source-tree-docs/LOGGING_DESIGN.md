# Ghar Sajag logging design — v1.1

## Purpose and safety boundary

The diagnostic subsystem records stable failure breadcrumbs without recording resident activity details, names, tokens, payloads, Wi-Fi credentials, precise timestamps of household events, or memory addresses. Logging helps reconstruct a failed flow; it cannot itself reliably detect an out-of-bounds access, double free, use-after-free, or arbitrary null dereference. Development builds therefore also run AddressSanitizer and UndefinedBehaviorSanitizer. The ESP-IDF binding must additionally enable the panic handler, watchdogs and coredump support.

## Two build profiles

| Profile | ERROR | TRACE | Intended use |
|---|---|---|---|
| Production | Always compiled and retained | Compiled out in C++; filtered in backend/app | Commercial delivery |
| Development | Retained | Function entry/exit or major transition | Lab diagnosis and HIL |

C++: `GS_ENABLE_TRACE=0` is the default. Run `make verify-trace` to compile with `GS_ENABLE_TRACE=1`.

Backend: `GS_TRACE=1` is a deployment-build setting. Default is disabled.

Browser: the build may inject `globalThis.__GS_TRACE__ = true`; production leaves it absent/false.

## Record contract

Each line is bounded and machine-readable:

`level=ERROR category=STORAGE module=H02 event=commit.failed detail=capacity_exhausted`

Fields are `level`, `category`, stable `module`, stable `event`, and a short allow-listed `detail`. Newlines are removed from app details. C++ records use a fixed 384-byte stack buffer and no formatting heap allocation.

## Categories and module identifiers

| Category | Modules |
|---|---|
| NODE / RADIO / STORAGE | N00 runtime, N01 sensing, N02 radio, N03 power, N04 lifecycle, N05 journal |
| HUB / RULES / STORAGE | H00 runtime, H01 ingest, H02 journal, H03 time, H04 coverage, H05 routines, H06 resident UI, H07 configuration, H08 cloud sync |
| SECURITY / RULES | S01 credentials and update policy; S00 shared rules |
| BACKEND | B01–B12 service modules |
| APP | A01–A05 user-application modules |
| TEST | T01 C++, T02 Python, T03 JavaScript verification |

## Storage and rotation

- Host C++ and backend write `.txt` files, rotate at 128 KiB, and retain two older files. ERROR records flush immediately in C++.
- The browser retains only the newest 128 records in memory and can export them as text. It has no continuous filesystem permission.
- ESP32 production binding should implement `gs::log::Sink` using a bounded wear-levelled partition or a small RTC/RAM ring plus persisted crash summary. Do not write flash on every trace.
- If the sink cannot open or storage is unavailable, business logic continues. Logging must never become a safety dependency.

## Failure breadcrumbs

Production ERROR is limited to flow-breaking conditions: exhausted journal/queue capacity, rejected unauthorized input, invalid credential material, uncaught backend validation/runtime failures, and failed application authorization/service requests. Expected states—no activity, privacy mode, ordinary retry, offline cloud, stale UI data—are not ERROR.

## Analysis

Run `python3 tools/logs/analyze_logs.py logs/<file>.txt`. The tool rejects malformed records and summarizes levels, categories, modules and events. Use event/module identifiers to correlate with the LLD; do not add raw resident payloads while debugging.

## Exit criteria

1. Production verification contains ERROR records and no TRACE records.
2. Development verification contains TRACE records for node, hub, rules/security, backend and app modules.
3. File and browser storage remain bounded.
4. Sanitizer tests pass.
5. No secret, resident name, event payload or full credential appears in a record.

