# Fresh R1 runtime host gate — 2026-10-05

Base: `cfec7d267b45ee4df94ab2c68e4dd8a45ccacafc`.
These are host results, not physical qualification. No board/dump writes occurred.

## Before the production correction

The new focused test started with an empty BlobStore/inventory and obtained
owner Ready through the real `HubDurabilityOwner` genesis. A fresh authenticated
registry save independently failed because GSRG v2 required migration metadata.
To isolate durability from that blocker, the pre-fix test supplied an enrolled
NodeRegistry descriptor with a nonzero authenticated owner digest. This isolation
fixture was removed from the final strict gate; it is not a registry workaround.

Observed before editing production:

```text
PRE_FIX registry_fresh_save=0
PRE_FIX DurableStore::commit=NotCommitted writes_no_transition=1
PRE_FIX checkpoint_domain=0 append_domain=1
PRE_FIX ACK=3 journal_size=0 last_ordinal=0
R1-FRESH-INSTALL FAIL first event must be Durable
```

Call path: runtime authenticated callback -> run_state_once -> HubJournal::commit
-> DurableJournalSlotStore::write/append_event -> DurableStore::commit. The
existing owner-domain check returns NotCommitted; the adapter returns false;
the journal reports StorageFault and the runtime returns Rejected. No transition
or reducer effect is created.

## Correction

Only genuine empty FreshInstallation genesis gets native registry ownership.
Checkpoint schema 4 uses the existing reserved flag bit 0x80 to authenticate the
native origin, with no size increase. The marker requires registry ownership,
zero migration frontier/table digest, and no migration/legacy flags. Old schemas
and legacy bootstrap keep their old meaning. No migration completion is minted.
Owner-domain checks in commit/recover remain enforced. Native ownership persists
through checkpoint publication and controlled empty-history epoch changes.

Fresh GSRG v2 snapshots use phase value 3, FreshInstallation, with zero migration
source metadata. Initial save selects it only for a missing snapshot and a clean
Uninitialized candidate. Existing v1/Prepared/Activated snapshots do not receive
that promotion. Previous readers reject these new native encodings fail-closed.

## Final gate

`make hub-fresh-install-host-test` passes. It exercises actual production codecs,
AEAD uplink authentication, authenticated registry persistence, durable slot
storage, HubRuntime ACK/reducer handling, and reboot reconstruction. It verifies:

- First event Durable after stored transition, one logical effect.
- Reboot Ready and old business EventKey replay in a newer transport session.
- Lost-ACK replay Durable with no additional logical effect.
- Native ownership survives another checkpoint and reboot.
- Wrong owner domain rejected; native roots cannot claim legacy slots.
- Failed event write produces Rejected, never Durable.
- Partial genesis remains closed across reboot.
- A fresh-install claim over unsupported legacy slots fails without writes.

The commissioning result is a trusted fixture; this test does not repeat the
separate mutual-proof commissioning/rejoin protocols or physical RF tests.

## Regression command and results

```sh
make -j4 hub-fresh-install-host-test hub-durable-storage-host-test hub-durable-provider-host-test registry-host-test registry-persistence-host-test hub-journal-migration-host-test hub-journal-persistence-host-test hub-retirement-snapshot-host-test
```

PASS: fresh installation, durable storage, durable provider, registry,
registry persistence, journal persistence, retirement snapshot.

FAIL: legacy journal migration at `clean migration commits`. This same assertion
fails when the unchanged cfec7d2 source/test snapshot is extracted into /tmp and
built using an isolated object directory. Legacy migration is not fixed here.
Combined make exits 2 because of that pre-existing failure.

An initial incremental run mixed old/new checkpoint object layouts. Generated
.d target paths included an equals sign, which make interpreted as an assignment.
Make now replaces equals signs in the object-directory component with underscores;
final validation rebuilt the affected translation units. No storage logic was
changed to address that build-artifact issue.

## Bench reset recommendation — design only

Preserve existing Hub forensic dumps. Before clearing Node recovery, capture and
hash its NVS evidence and archive the association plus 28 retained development
records securely; do not print keys or payloads in reports.

For an explicitly retired development installation, initialize gs_journal and
replace only Hub gs_security/wrap_key, gs_home/id, and gs_registry/snapshot.
Preserve identity/factory material, unrelated normal-NVS data, bootloader,
partition table, otadata, phy_init and OTA layout. A future controlled initializer
must create new wrapping/Home state consistently and verify native genesis;
normal firmware must not treat unexplained erased journal state as fresh.

On the Node, preserve device identity, wrapping/factory material and monotonic
gs_node/boot_session. Explicitly discard the archived development recovery
snapshot at gs_node_rec/snapshot and unpair through AssociationRepository's
factory_reset generation progression, then commission into the new Home. Do not
manufacture Durable ACKs for old records or migrate them into the new installation.
A coordinated initializer is still required; none was implemented/executed.

After provisioning: normal fresh boot -> owner Ready -> authenticated registry
and Node -> one Durable event -> Hub reboot -> Ready -> duplicate replay with one
logical effect -> Node retained=0/in_flight=0 -> resume C8.
The separate 128-event lifetime exhaustion bug remains an R1 blocker.
