# 1.5.0 — local simulation integration

Added interactive C++ host adapter, Python lab API, connected dashboard, 13 scenario assertions, 9 HTTP checks and optional browser script. Existing domain algorithms unchanged; product version metadata updated. Documentation v2.0 remains the design baseline with a new simulation LLD/guide.

# 1.4.2 documentation and traceability patch

Added canonical module/requirement responsibility comments and critical API intent. Product version metadata updated. Runtime algorithms unchanged. Documentation edition 2.0 supersedes earlier design/status summaries.

# Release 1.4.1

Documentation/status synchronization and Product::version metadata patch. No core algorithm or interaction API change. Fresh product tests are recorded in PATCH_VERIFICATION.txt.

# Release 1.4.0

- Added Parivar Saathi and Sarthi-AI product selection to the host build.
- Added allocation-free interaction lifecycle with an asynchronous provider port.
- Added per-product regression tests and a two-product verification target.
- Added product-family HLD, interaction LLD, architecture and sequence diagrams.
- Added current progress summary with explicit remaining integration gates.

Migration: extract this release alongside v1.3; preserve local changes before
merging. From this directory in Ubuntu, run `make verify-products`. Do not copy
generated build or log output to the firmware source tree in Git.

This is a new release snapshot based on the available prior reference source.
It does not modify a remote Git repository or replace historical documents.
Product names affect the new C++ profile; public website and old document titles
are not renamed. AI conversation/audio and flashable ESP-IDF projects remain
future integration work.
