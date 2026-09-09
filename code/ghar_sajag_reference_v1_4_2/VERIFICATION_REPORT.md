# Reference code 1.4.2 verification

The fresh `make verify-products` transcript is at `../../evidence/Verification_v1.4.2.txt`.
Both profiles passed: 57 C++ checks, 13 Python tests and 8 JavaScript tests per profile,
plus contract structure checks, simulator/matrix and product lifecycle tests.

`Artifact_Validation.txt` records comparison with source 1.4.1: executable changes
are limited to Product::version metadata; the remaining source differences are
comments/blank lines. Python ASTs were also compared. The later NFR-ID comments
do not change executable behaviour.

This is host evidence, not full requirement conformance or an ESP32 hardware run.
Real radio, flash, FreeRTOS, production backend/provider/UI and installed-home
qualification remain pending. The v2.0 open-work register documents audit findings.
Historical verification files are retained under their original version names.
