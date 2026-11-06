# GS-117 installed-device receipt mechanism audit — 2026-11-06

## Result

**No-go for device access until the existing receipt procedure and its audited
authorization scope can cover the exact requested evidence.** This was an
offline-only review. No serial port, device, readback command, reset, bootstrap,
firmware, or authorization ledger was accessed or changed.

GS-117 remains Highest / In Progress. Installed firmware remains unchanged;
the installed-image receipts are STALE; the physical entitlement #11897 remains
`SAFETY_LATCHED` with 1/1 attempts consumed; historical #11886 is preserved;
`TC001_READY=NO`; TC-001 is 0/5.

## Repository and preflight

- Canonical worktree: `/home/udaybhan/projects/Ghar_sajag_r1`.
- Branch: `feature/r1-commercial-baseline`.
- Local and `origin/feature/r1-commercial-baseline` HEAD:
  `88685c82b1b58d6148e8f7c653431e3261faf15f`.
- Context preflight: PASS, context `2026-10-28.001`.
- No tracked changes on entry. The 79 pre-existing untracked status entries
  remain untouched. Older worktrees are unchanged.
- Latest GS-117 owner/status comments reviewed: #11925 and #11926.

## Existing procedure inventory

| Existing artifact | SHA-256 | Offline finding | Use decision |
|---|---|---|---|
| `~/.local/state/ghar-sajag/gs117-tc001/provenance-refresh-20261031T0501Z/procedure/readback_once_v2.py` | `87fa118c5c345d8544c25f35b45966a6e41e5354fcfe9e1255dff019b620d25b` | Historical procedure reads the partition table, both OTA metadata copies and selected application bytes. It does not read the bootloader. C3 uses no-reset ROM connection; S3 uses default-reset connection. Existing historical receipt is stale. | Does not satisfy the requested current evidence or rollback provenance. |
| `~/.local/state/ghar-sajag/gs117-tc001/provenance-refresh-20261101/candidate/readback_once_v3.py` | `d1895a348612ae93395fb03ceb69517619c85ecde8fb8a7b9ea89af0d0064ca4` | Existing offline candidate verifies fixture USB/MAC/chip/security identity, exact expected partition map, selector copies and selected app bytes using direct RAM-stub reads. It does not read bootloader bytes. It enters ROM and restores normal boot with one USB-aware EN reset per target (up to two reset transitions per target). | Best reusable base, but incomplete for this scope and not executed on hardware. |
| `.../candidate/test_readback_once_v3_offline.py` | `b68756da8cc47fcf989bfa41cb0b52e09074754a6e67546acdf76a91eb3cbede` | Prior mocked offline evidence is 22/22; no physical qualification. | Historical test evidence only. |
| `~/.local/state/ghar-sajag/gs117-tc001/cache-deploy-20261026T082637Z/operator-session-sources/read-current-s3.py` | `aea8250d905fe13c671e5312b83bb104347741a2b42f94a4e53407ae74540b38` | Broad S3 capture includes NVS and unrelated flash/state reads and invokes the broader esptool read path. | Rejected for this minimum-evidence request. |

The v3 procedure writes private evidence under protected local state and reads
only the pinned table, selector metadata and active application region. Its
resets are real target runtime changes despite the read-only flash scope. They
must be called out in an operation approval. Its existing candidate hash cannot
pin a bootloader read that the code does not perform.

## Authorization and recovery provenance

`code/tools/local/gs117_hil_authorization.py` currently lists `readback` under
`PROHIBITED`; its allowed DEV procedures do not include an installed-image
receipt operation. The consumed #11897 entitlement cannot be reused or changed
to perform this read. No replacement authorization was created.

The historical installed S3 bootloader digest is
`ae304441aaaad2b52765d48f4b37752f2ab26a65a480f5f1f9586cd54ebe1580`, but it
has no trusted matching source/build/configuration provenance. The diagnostic
build's rollback-enabled bootloader has a different digest. A fresh readback
hash alone would establish current bytes, not which trusted configuration
produced them. GS-D029's application rollback requirement remains in force;
installation remains **NO-GO** unless the installed bootloader is tied to
trusted rollback-capable build/configuration evidence.

## Prepared operation scope and owner decision

The required minimal capture, if a compatible reviewed procedure and separate
audited readback authorization are approved, is limited to:

- Fixture: `gs177-test-product`; C3 `c3-146393c5d158` / COM4 / USB
  `14:63:93:C5:D1:58`; S3 `hub-e072a1d38d34` / COM10 / USB
  `E0:72:A1:D3:8D:34`.
- Device hardware identity; current C3/S3 active application identity/digest;
  S3 bootloader identity/digest; partition table; both OTA selector copies and
  active slot.
- For the missing S3 bootloader digest, the minimum additional flash range is
  the existing bootloader region `0x000000..0x008000` (32 KiB), subject to the
  reviewed procedure's range guard. Existing v3 already reads table
  `0x008000..0x009000`, OTA metadata `0x00f000..0x011000`, and only the selected
  application image bytes.
- No NVS, credentials, keys, eFuses, unrelated partitions, general flash dump,
  writes, erase, selector change, firmware update, bootstrap, motion/event, or
  radio observation.
- If based on v3, the scope must explicitly include its one ROM-entry and one
  USB-aware EN restore reset per target, or the revised reviewed procedure must
  prove a reset-free path. No retry. Stop on any identity, hash, security,
  authorization, or layout mismatch.

**Owner decision requested before device access:** authorize the narrowly
scoped offline update of the existing v3 receipt procedure and its focused tests
to add only the S3 bootloader-region read, and authorize adding a distinct,
one-use `readback_receipt` operation to the existing audited authorization
allowlist without changing #11886/#11897 or granting firmware/hardware-test
rights. This is *not* device-access approval. Once the exact revised tool/test
hashes and authorization representation are reviewed, submit one exact-hash,
one-use capture authorization before opening either serial port. The capture
must not proceed if that approval is absent.

This decision request was recorded on GS-117 in Jira comment #11927. It does not
represent approval or activation of either the procedure change or the device
operation.

Even if capture succeeds, automatic rollback provenance still needs a trusted
match for the installed bootloader bytes and configuration. Do not infer it
from a hash, partition map, manual restore, or candidate build setting alone.

## Validation and delivery state

- Newly run checks: context preflight PASS; SHA-256 recomputation for the four
  private candidates and current authorization source PASS; repository/branch/
  remote/status inspection PASS.
- Reused historical evidence: v3 offline mocks 22/22. No tests were rerun.
- Hardware/COM/reset/readback/authorization operations: **NONE**.
- Firmware: unchanged. Receipts: STALE. Rollback provenance: UNVERIFIED.
- Candidate installation: NO-GO. `TC001_READY=NO`; TC-001 0/5.
- Next action: owner decision on the minimal existing-procedure and
  authorization-allowlist correction described above; then hash-pin and review
  it before requesting the one-use device capture authorization.
