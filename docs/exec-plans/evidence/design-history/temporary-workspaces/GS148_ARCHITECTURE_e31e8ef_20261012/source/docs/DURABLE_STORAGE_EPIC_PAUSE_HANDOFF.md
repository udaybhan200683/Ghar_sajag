# Durable Storage Epic Pause Handoff

**Status:** WIP checkpoint for an intentionally paused feature branch. The legacy
migration coordinator is deferred beyond Ghar Sajag R1. This handoff preserves the
current implementation and records where work resumes; it does not certify production
completion.

## Repository checkpoint

- Worktree: `/home/udaybhan/projects/Ghar_sajag_durable_storage_impl`
- Branch: `feature/hub-durable-storage-primitives`
- Base HEAD before this WIP checkpoint: `072316a5b376acc16860ee58a2d351a1dce46f6e`
- WIP checkpoint commit message: `WIP: checkpoint deferred durability migration`
- The working diff was intentionally dirty and has been preserved in the checkpoint.
- No other Ghar Sajag checkout is part of this work.

## Exact files in the checkpoint

Modified before adding this handoff:

1. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/G01_ENROLLMENT_OWNERSHIP_MIGRATION_CONTRACT.md`
2. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/registry/node_registry.cpp`
3. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/registry/node_registry.hpp`
4. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/registry/registry_persistence.cpp`
5. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/registry/registry_persistence.hpp`
6. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/durable_journal_slot_store.cpp`
7. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/durable_journal_slot_store.hpp`
8. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/durable_transition.cpp`
9. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/durable_transition.hpp`
10. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/hub_durability_owner.cpp`
11. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/hub_durability_owner.hpp`
12. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/node_retirement_snapshot.cpp`
13. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/node_retirement_snapshot.hpp`
14. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/hub_runtime_adapter.cpp`
15. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/hub_security_link.cpp`
16. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/hub_security_link.hpp`
17. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/nvs_durable_blob_store.cpp`
18. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/nvs_durable_blob_store.hpp`
19. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/nvs_store_inventory.cpp`
20. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/cpp/hub_durable_provider_validation.cpp`
21. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/cpp/hub_durable_storage_validation.cpp`
22. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/cpp/hub_journal_migration_validation.cpp`
23. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/cpp/hub_retirement_snapshot_validation.cpp`
24. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/cpp/node_registry_validation.cpp`
25. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/cpp/registry_persistence_validation.cpp`
26. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/python/test_node_retirement_protocol_model.py`

Untracked before adding this handoff:

27. `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/python/test_g01_coordinator_crash_model.py`

This handoff is the additional checkpoint file:

28. `docs/DURABLE_STORAGE_EPIC_PAUSE_HANDOFF.md`

## Architecture authority and test state

- Architecture contract: `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/G01_ENROLLMENT_OWNERSHIP_MIGRATION_CONTRACT.md`
- Final coordinator closure and implementation handoff: contract §20, especially §20.10.
- Abstract crash model: `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/python/test_g01_coordinator_crash_model.py`

Focused passing gates:

- `make registry-host-test` — PASS
- `make registry-persistence-host-test` — PASS
- `make hub-retirement-snapshot-host-test` — PASS
- `make hub-durable-storage-host-test` — PASS
- `make hub-durable-provider-host-test` — PASS
- `python3 -B tests/python/test_g01_coordinator_crash_model.py` — PASS, 37 tests

Known focused failure:

- `make hub-journal-migration-host-test` — FAIL at `clean migration commits`.
- Cause: the partial legacy helper attempts to commit registry-domain Events while the
  selected checkpoint/root is still legacy-domain. `DurableStore::commit()` correctly
  rejects the domain mismatch. Keep that validation intact. The production migration
  coordinator and candidate/publication root are not implemented.
- Do not spend time trying to make this gate pass by weakening domain checks. Legacy
  v1-to-v2 live migration is deferred beyond R1.

Other recorded results:

- Hub ESP32 target build — PASS in the prior implementation continuation; not rerun for
  this pause checkpoint.
- Node target build — NOT RUN; Node firmware was not changed.
- Broad `cpp-test` and `validation-fast` — NOT RUN after the migration gate failure.
- `git diff --check` — PASS before checkpoint.

## Implementation state

Implemented or independently passing portions:

- Stable ten-slot registry ownership descriptors, slot/generation persistence and
  registry-derived owner resolution scaffolding.
- GSRG v2 serialization/validation scaffolding and deterministic preparation helpers.
- Schema-2 compact retirement snapshot encoding, occupancy-mask representation, and
  schema-1 inspection support.
- Exact conditional erase primitive with focused provider/storage coverage.
- GMM2 fixed-size authenticated A/B codec/repository scaffolding and phase/frontier
  validation tests.
- GCP3 checkpoint metadata/domain gates and the 4,549-byte cap.
- Storage provider key mapping, inventory and current retirement write cap adjustments.
- Abstract crash model covering 37 tests.

Partial or incomplete portions:

- Production v1-to-v2 preparation is not integrated with intent-first runtime migration
  or final registry activation.
- No production bounded migration coordinator constructs and verifies candidate roots.
- G05 intent-owned staged-object inventory, source release and exact cleanup are not
  integrated end to end.
- Selector/publication barrier, legal shadow/fallback recovery, frontier advancement,
  and final joint table/root activation are incomplete.
- Runtime migration traffic freeze and post-activation fresh-rejoin flow are incomplete.
- `migrate_legacy_journal()` remains the old helper and is not a valid substitute for
  the §20 coordinator.
- Production crash-cut coverage and actual implementation storage-budget certification
  are incomplete.

The focused passing gates and abstract model do not establish full production migration
completion. No architecture contradiction was found.

## Product scope decision

### R1 required durability

- Fresh/current-format installation
- Reliable current-format persistence
- Normal reboot recovery
- Duplicate protection
- Authenticated current ownership
- Versioned persistence for future FOTA evolution
- Fail-closed corruption handling

`R1_FRESH_INSTALL_DURABILITY_PROVEN=NO`. Current code has useful registry/storage
primitives and passing focused tests, but fresh-install joint GSRG/root activation and
end-to-end current-format runtime proof remain incomplete. Resolve and validate this R1
scope without implementing legacy migration.

### Post-R1 deferred

- Legacy v1-to-v2 live migration
- Complete G01/G02/G05 migration coordinator
- Migration shadow/fallback publication machinery
- Exhaustive migration crash/power-cut qualification
- Full logical event reclamation
- Removal of the 128-event retention limit

## Storage model and qualification status

These are **ARCHITECTURE MODEL** values from contract §20.9, not production
certification:

- Modeled used entries: 3,224
- Modeled free entries: 808
- Modeled free-entry margin: 20.0396825397%
- Modeled used bytes: 88,976
- Modeled free bytes: 42,096

`NEW_PERSISTENT_KEYS=0`
`NEW_SCRATCH_KEYS=0`
`KNOWN_128_EVENT_RETENTION_LIMIT=YES`
`PHYSICAL_GC_QUALIFICATION=NOT_RUN`
`POWER_CUT_QUALIFICATION=NOT_RUN`

Do not report the architecture ledger as actual production usage until the production
coordinator and complete object coexistence plan have been implemented and rederived.

## Resume points

Immediate R1 work is to prove fresh/current-format boot, persistence, reboot recovery,
authenticated owner binding, duplicate handling and fail-closed corruption through the
production runtime and its focused tests. Keep migration traffic/legacy behavior closed
where the required coordinator is absent.

When post-R1 legacy migration is explicitly resumed, use contract §20.10 in order. The
exact first migration implementation step is §20.10 item 1:
`firmware/hub/components/storage/durable_transition.{hpp,cpp}` — finish manifest/root
recovery and implement exact candidate staging, verification, publication, shadowing,
release and bounded coordinator resume. Continue with registry persistence/NodeRegistry,
retirement snapshot, durability owner, runtime/security integration, and production crash
tests in the order listed there. Do not restart from a clean checkout, weaken domain
validation, create scratch keys, or treat this handoff's modeled budget as a production
certificate.
