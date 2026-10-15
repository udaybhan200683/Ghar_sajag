# Native validation evidence archive — candidate 3b69336

Every `.md`-suffixed report, log and source checksum manifest in this directory is a byte-exact copy of the native file at the listed original path. The suffix is used so the committed evidence remains excluded by the existing source fingerprint rule (which excludes Markdown files); the native bytes are otherwise unchanged.

- `final-pwa-report.json.md` and `final-*.log.md`: `code/evidence/validation_framework/pwa-1792047364328622824/` (source HEAD 3b69336, fingerprint `a468c9311fa3c9942c0485b52138574c1641026fc797400cc27ca6850bf949c9`); 14 stages PASS, P0 full-product stage FAIL with `product_status=PARTIAL`.
- `fresh-pwa-report.json.md` and `fresh-*.log.md`: `code/evidence/validation_framework/pwa-1792046117596214866/` (full fresh run at source 63cf8d6, same source fingerprint).
- `canonical-*.log.md`: six fresh canonical C8/storage/CloudSync stage logs from `code/evidence/validation_framework/final-canonical-rerun-63cf8d6/`.
- `source-final-candidate-SHA256SUMS.md` and `source-canonical-rerun-SHA256SUMS.md`: byte-exact copies of the native manifests. The final candidate manifest was verified from the `code/` directory before archival; the canonical rerun manifest is verified with this archive manifest.
- `SHA256SUMS.md`: archive-level SHA-256 manifest for all copied native files. Run `sha256sum -c SHA256SUMS.md` in this directory.

Historical native failure receipts are preserved unchanged. This archive does not alter commercial qualification status: P0 remains PARTIAL, migration FAIL, old-reader rollback limitation remains, CloudSync production PENDING, and physical qualification NOT_RUN.

## Existing whitespace findings

The copied native logs are preserved byte-for-byte. `git diff --check` reports trailing spaces in the native dummy-stream PASS lines and the P0 runner command line (`final-dummy-streams.log.md`, `fresh-dummy-streams.log.md`, and `final-p0-full-product-e2e.log.md`, line 67; the fresh P0 log has the same command). These spaces were present in the original receipts and have not been trimmed or rewritten. The earlier validation record also documents the historical imported-log whitespace findings.
