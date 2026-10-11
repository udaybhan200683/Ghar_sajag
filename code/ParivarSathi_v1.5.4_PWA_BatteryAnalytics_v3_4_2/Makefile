CXX ?= g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra -Werror -pedantic
# ESP-IDF activation can prepend its esp32ulp-elf directory, whose `ld`
# cannot link host x86_64 binaries. Keep host validation independent of that
# ambient PATH while leaving the selected host compiler configurable.
HOST_TOOLCHAIN_GUARD ?= -B/usr/bin
HOST_CXX = $(CXX) $(HOST_TOOLCHAIN_GUARD)
TRACE_FLAGS ?= -DGS_ENABLE_TRACE=0
PRODUCT ?= base
ifeq ($(PRODUCT),base)
PRODUCT_FLAGS := -DGS_PRODUCT_AI=0
else ifeq ($(PRODUCT),ai)
PRODUCT_FLAGS := -DGS_PRODUCT_AI=1
else
$(error PRODUCT must be base or ai)
endif
CXXFLAGS += $(PRODUCT_FLAGS)
INCLUDES := -Ibuild/gs40_generated -I. -Ishared/include -Ifirmware/node/components -Ifirmware/hub/components -Ifirmware/common/security

CPP_SOURCES := \
	shared/src/rules.cpp \
	shared/src/logging.cpp \
	host/logging/file_log_sink.cpp \
	firmware/common/transport/data_plane_codec.cpp \
	firmware/common/transport/node_retirement_protocol.cpp \
	firmware/common/transport/session_id.cpp \
	firmware/node/components/sensing/sensing.cpp \
	firmware/node/components/radio/node_radio.cpp \
	firmware/node/components/power/power.cpp \
	firmware/node/components/lifecycle/lifecycle.cpp \
	firmware/node/components/storage/node_store.cpp \
	firmware/node/fota/fota_receiver.cpp \
	firmware/node/runtime/node_runtime.cpp \
	firmware/hub/components/ingest/ingest.cpp \
	firmware/hub/components/registry/node_registry.cpp \
	firmware/hub/components/storage/journal.cpp \
	firmware/hub/components/storage/durable_transition.cpp \
	firmware/hub/components/storage/node_retirement_snapshot.cpp \
	firmware/hub/components/storage/hub_durability_owner.cpp \
	firmware/hub/components/storage/durable_journal_slot_store.cpp \
	firmware/hub/components/time/clock.cpp \
	firmware/hub/components/coverage/coverage.cpp \
	firmware/hub/components/rules/routine_service.cpp \
	firmware/hub/components/ui/resident_ui.cpp \
	firmware/hub/components/lifecycle/config_service.cpp \
	firmware/hub/components/cloud/cloud_sync.cpp \
	firmware/hub/runtime/hub_runtime.cpp \
	firmware/hub/runtime/hub_checkpoint_codec.cpp \
	firmware/hub/components/storage/runtime_state_store.cpp \
	firmware/common/security/security.cpp

# Reuse the large production translation units across host validation binaries.
# Include the selected product/trace flags in the object directory so switching
# validation modes cannot silently reuse objects built with different defines.
# An equals sign in a dependency target is parsed as a make assignment.
# Keep generated .d target paths usable when a checkpoint header changes.
HOST_BUILD_PROFILE := $(shell python3 scripts/host_build_profile.py "$(HOST_CXX)" "$(CXXFLAGS)" "$(TRACE_FLAGS)" "$(INCLUDES)")
CPP_OBJECT_DIR := build/obj/$(PRODUCT)/$(HOST_BUILD_PROFILE)
CPP_OBJECTS := $(patsubst %.cpp,$(CPP_OBJECT_DIR)/%.o,$(CPP_SOURCES))
CPP_EXTRA_SOURCES := firmware/common/transport/fota_secure_wire.cpp firmware/node/fota/boot_health_gate.cpp
host_objects = $(patsubst %.cpp,$(CPP_OBJECT_DIR)/%.o,$(1))
CPP_EXTRA_OBJECTS := $(patsubst %.cpp,$(CPP_OBJECT_DIR)/%.o,$(CPP_EXTRA_SOURCES))
CPP_DEPENDENCIES := $(CPP_OBJECTS:.o=.d) $(CPP_EXTRA_OBJECTS:.o=.d)

-include $(CPP_DEPENDENCIES)

$(CPP_OBJECTS) $(CPP_EXTRA_OBJECTS): Makefile build/gs40_generated/gs/node_health_config.hpp
$(CPP_OBJECT_DIR)/%.o: %.cpp
	mkdir -p $(dir $@)
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) -MMD -MP -MF $(@:.o=.d) -c $< -o $@

.PHONY: all verify cpp-test hub-recovery-scheduling-host-test hub-fresh-install-host-test hub-durable-storage-host-test hub-durable-provider-host-test hub-journal-migration-host-test hub-retirement-snapshot-host-test battery-c8-host-test master-validation master-validation-self-test fota-host-test hub-fota-guard-host-test secure-fota-adapter-host-test multinode-host-test registry-host-test registry-persistence-host-test hub-journal-persistence-host-test hub-backend-commit-host-test commissioning-crypto-host-test rejoin-host-test association-host-test node-recovery-host-test node-recovery-persistence-host-test node-retirement-protocol-host-test simulator simulate-matrix python-test app-test contracts clean validation-fast release-gate release-gate-browser manual-test-plan functional-test dummy-sensor-test coverage-test performance-profile performance-test stress-test concurrency-test endurance-test hw-validation-fast hw-pair-build hw-release-gate validation-nightly validation-coverage hil-setup hil-preflight hil-smoke hil-regression hil-qualify hil-checkpoint-smoke hil-checkpoint-fota hil-secure-signed-fota hil-checkpoint-secure-signed-fota hil-fota hil-supervisor-test hil-tooling-test hil-host-check hil-target-build-check s3-fixture-commissioning-test physical-hil-catalogue-test validation-p0-e2e validation-board-hil validation-motion-hil gs130-hil-runner-test
.PHONY: s3-durable-outbox-host-test hub-segmented-outbox-runtime-host-test

BATTERY_C8_SOURCES := shared/src/logging.cpp firmware/node/components/sensing/sensing.cpp firmware/node/components/power/power.cpp firmware/node/components/radio/node_radio.cpp firmware/node/components/storage/node_store.cpp firmware/node/runtime/node_runtime.cpp
BATTERY_C8_OBJECTS := $(patsubst %.cpp,$(CPP_OBJECT_DIR)/%.o,$(BATTERY_C8_SOURCES))

all: verify

build/gs40_generated/gs/node_health_config.hpp: config/node_health.json scripts/generate_node_health_config.py backend/ghar_sajag/node_health_policy.py
	python3 scripts/generate_node_health_config.py --output $@
	touch $@

build: build/gs40_generated/gs/node_health_config.hpp
	mkdir -p build logs

GS116_CPP_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_CPP_TEST_HOST_SOURCES))
cpp-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_CPP_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_CPP_TEST_HOST_SOURCES)) tests/cpp/test_main.cpp -lcrypto -o build/cpp_tests
	./build/cpp_tests

GS116_MASTER_VALIDATION_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_MASTER_VALIDATION_HOST_SOURCES))
master-validation: build $(CPP_OBJECTS) $(call host_objects,$(GS116_MASTER_VALIDATION_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_MASTER_VALIDATION_HOST_SOURCES)) tests/cpp/master_validation.cpp -o build/master_validation
	python3 tools/validation/master_validation.py

battery-c8-host-test: build $(BATTERY_C8_OBJECTS)
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(BATTERY_C8_OBJECTS) tests/cpp/battery_c8_validation.cpp -o build/battery_c8_validation
	./build/battery_c8_validation
	PYTHONPATH=tests/python python3 -m unittest test_battery_power_invariants -v

.PHONY: gs40-host-test gs40-config-test
gs40-config-test: build
	PYTHONPATH=backend:tests/python python3 -m unittest test_node_health_config -v

GS116_GS40_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/common/security/runtime_frame_security.cpp firmware/common/security/rejoin_protocol.cpp firmware/node/components/storage/node_recovery_persistence.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_GS40_HOST_TEST_HOST_SOURCES))
gs40-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_GS40_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_GS40_HOST_TEST_HOST_SOURCES)) tests/cpp/gs40_node_health_validation.cpp -lcrypto -o build/gs40_node_health_validation
	./build/gs40_node_health_validation

.PHONY: gs150-host-test
GS116_GS150_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/common/security/runtime_frame_security.cpp firmware/common/security/rejoin_protocol.cpp firmware/node/components/storage/node_recovery_persistence.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_GS150_HOST_TEST_HOST_SOURCES))
gs150-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_GS150_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_GS150_HOST_TEST_HOST_SOURCES)) tests/cpp/gs150_offline_sleep_validation.cpp -lcrypto -o build/gs150_offline_sleep_validation
	./build/gs150_offline_sleep_validation

GS116_MASTER_VALIDATION_SELF_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_MASTER_VALIDATION_SELF_TEST_HOST_SOURCES))
master-validation-self-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_MASTER_VALIDATION_SELF_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_MASTER_VALIDATION_SELF_TEST_HOST_SOURCES)) tests/cpp/master_validation.cpp -o build/master_validation
	python3 tools/validation/master_validation.py --self-test

GS116_FOTA_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_FOTA_HOST_TEST_HOST_SOURCES))
fota-host-test: build $(CPP_OBJECTS) $(CPP_EXTRA_OBJECTS) $(call host_objects,$(GS116_FOTA_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(CPP_EXTRA_OBJECTS) $(call host_objects,$(GS116_FOTA_HOST_TEST_HOST_SOURCES)) tests/cpp/fota_host_validation.cpp -o build/fota_host_validation
	./build/fota_host_validation

GS116_HUB_FOTA_GUARD_HOST_TEST_HOST_SOURCES := firmware/common/transport/fota_secure_wire.cpp firmware/common/security/runtime_frame_security.cpp firmware/hub/components/registry/node_registry.cpp firmware/hub/components/fota/hub_fota_guard.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_FOTA_GUARD_HOST_TEST_HOST_SOURCES))
hub-fota-guard-host-test: build $(call host_objects,$(GS116_HUB_FOTA_GUARD_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_HUB_FOTA_GUARD_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_fota_guard_validation.cpp -lcrypto -o build/hub_fota_guard_validation
	./build/hub_fota_guard_validation

GS116_SECURE_FOTA_ADAPTER_HOST_TEST_HOST_SOURCES := firmware/common/transport/fota_secure_wire.cpp firmware/common/security/runtime_frame_security.cpp firmware/node/fota/fota_receiver.cpp firmware/node/fota/secure_fota_adapter.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_SECURE_FOTA_ADAPTER_HOST_TEST_HOST_SOURCES))
secure-fota-adapter-host-test: build $(call host_objects,$(GS116_SECURE_FOTA_ADAPTER_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_SECURE_FOTA_ADAPTER_HOST_TEST_HOST_SOURCES)) tests/cpp/secure_fota_adapter_validation.cpp -lcrypto -o build/secure_fota_adapter_validation
	./build/secure_fota_adapter_validation

GS116_MULTINODE_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/node/components/storage/node_recovery_persistence.cpp firmware/common/security/commissioning_protocol.cpp firmware/common/security/rejoin_protocol.cpp firmware/common/security/runtime_frame_security.cpp host/security/openssl_commissioning_crypto.cpp host/multinode/scheduled_harness.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_MULTINODE_HOST_TEST_HOST_SOURCES))
multinode-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_MULTINODE_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_MULTINODE_HOST_TEST_HOST_SOURCES)) tests/cpp/multinode_host_validation.cpp -lcrypto -o build/multinode_host_validation
	./build/multinode_host_validation
	python3 tools/validation/check_multinode_summary.py build/multinode_host_summary.json

GS116_REGISTRY_HOST_TEST_HOST_SOURCES := firmware/hub/components/registry/node_registry.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_REGISTRY_HOST_TEST_HOST_SOURCES))
registry-host-test: build $(call host_objects,$(GS116_REGISTRY_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_REGISTRY_HOST_TEST_HOST_SOURCES)) tests/cpp/node_registry_validation.cpp -o build/node_registry_validation
	./build/node_registry_validation

GS116_REGISTRY_PERSISTENCE_HOST_TEST_HOST_SOURCES := firmware/hub/components/registry/node_registry.cpp firmware/hub/components/registry/registry_persistence.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_REGISTRY_PERSISTENCE_HOST_TEST_HOST_SOURCES))
registry-persistence-host-test: build $(call host_objects,$(GS116_REGISTRY_PERSISTENCE_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_REGISTRY_PERSISTENCE_HOST_TEST_HOST_SOURCES)) tests/cpp/registry_persistence_validation.cpp -lcrypto -o build/registry_persistence_validation
	./build/registry_persistence_validation

GS116_HUB_JOURNAL_PERSISTENCE_HOST_TEST_HOST_SOURCES := shared/src/logging.cpp shared/src/rules.cpp firmware/common/transport/node_retirement_protocol.cpp firmware/hub/components/storage/journal.cpp firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/storage/durable_transition.cpp firmware/hub/components/storage/node_retirement_snapshot.cpp firmware/hub/components/storage/hub_durability_owner.cpp firmware/hub/components/ingest/ingest.cpp firmware/hub/components/coverage/coverage.cpp firmware/hub/components/rules/routine_service.cpp firmware/hub/runtime/hub_runtime.cpp firmware/hub/runtime/hub_checkpoint_codec.cpp firmware/hub/components/storage/runtime_state_store.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_JOURNAL_PERSISTENCE_HOST_TEST_HOST_SOURCES))
hub-journal-persistence-host-test: build $(call host_objects,$(GS116_HUB_JOURNAL_PERSISTENCE_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_HUB_JOURNAL_PERSISTENCE_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_journal_persistence_validation.cpp -lcrypto -o build/hub_journal_persistence_validation
	./build/hub_journal_persistence_validation

GS116_HUB_DURABLE_STORAGE_HOST_TEST_HOST_SOURCES := firmware/common/transport/data_plane_codec.cpp firmware/common/transport/node_retirement_protocol.cpp firmware/hub/components/storage/durable_transition.cpp firmware/hub/components/storage/node_retirement_snapshot.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_DURABLE_STORAGE_HOST_TEST_HOST_SOURCES))
hub-durable-storage-host-test: build $(call host_objects,$(GS116_HUB_DURABLE_STORAGE_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_HUB_DURABLE_STORAGE_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_durable_storage_validation.cpp -lcrypto -o build/hub_durable_storage_validation
	./build/hub_durable_storage_validation

GS116_HUB_FRESH_INSTALL_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/registry/registry_persistence.cpp firmware/common/security/runtime_frame_security.cpp firmware/hub/target/esp32/nvs_durable_key_codec.cpp firmware/common/security/rejoin_protocol.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_FRESH_INSTALL_HOST_TEST_HOST_SOURCES))
hub-fresh-install-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_FRESH_INSTALL_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_FRESH_INSTALL_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_fresh_install_validation.cpp -lcrypto -o build/hub_fresh_install_validation
	./build/hub_fresh_install_validation

hub-recovery-scheduling-host-test: build $(CPP_OBJECTS)
	$(HOST_CXX) $(CXXFLAGS) -DGS_RECOVERY_SCHEDULING_TEST=1 $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/registry/registry_persistence.cpp firmware/common/security/runtime_frame_security.cpp firmware/hub/target/esp32/nvs_durable_key_codec.cpp firmware/common/security/rejoin_protocol.cpp host/security/openssl_commissioning_crypto.cpp tests/cpp/hub_fresh_install_validation.cpp -lcrypto -o build/hub_recovery_scheduling_validation
	./build/hub_recovery_scheduling_validation

GS116_HUB_DURABLE_PROVIDER_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/target/esp32/nvs_durable_key_codec.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_DURABLE_PROVIDER_HOST_TEST_HOST_SOURCES))
hub-durable-provider-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_DURABLE_PROVIDER_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_DURABLE_PROVIDER_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_durable_provider_validation.cpp -lcrypto -o build/hub_durable_provider_validation
	./build/hub_durable_provider_validation

GS116_HUB_JOURNAL_MIGRATION_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/target/esp32/nvs_durable_key_codec.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_JOURNAL_MIGRATION_HOST_TEST_HOST_SOURCES))
hub-journal-migration-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_JOURNAL_MIGRATION_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_JOURNAL_MIGRATION_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_journal_migration_validation.cpp -lcrypto -o build/hub_journal_migration_validation
	./build/hub_journal_migration_validation

GS116_HUB_BACKEND_COMMIT_HOST_TEST_HOST_SOURCES := shared/src/logging.cpp firmware/hub/components/storage/journal.cpp firmware/hub/components/cloud/cloud_sync.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_BACKEND_COMMIT_HOST_TEST_HOST_SOURCES))
hub-backend-commit-host-test: build $(call host_objects,$(GS116_HUB_BACKEND_COMMIT_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_HUB_BACKEND_COMMIT_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_backend_commit_validation.cpp -lcrypto -o build/hub_backend_commit_validation
	./build/hub_backend_commit_validation

GS116_S3_DURABLE_OUTBOX_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/storage/journal.cpp shared/src/logging.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_S3_DURABLE_OUTBOX_HOST_TEST_HOST_SOURCES))
s3-durable-outbox-host-test: build $(call host_objects,$(GS116_S3_DURABLE_OUTBOX_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_S3_DURABLE_OUTBOX_HOST_TEST_HOST_SOURCES)) tests/cpp/durable_event_outbox_validation.cpp -lcrypto -o build/durable_event_outbox_validation
	./build/durable_event_outbox_validation

GS116_HUB_SEGMENTED_OUTBOX_RUNTIME_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/storage/outbox_journal_backend.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_SEGMENTED_OUTBOX_RUNTIME_HOST_TEST_HOST_SOURCES))
hub-segmented-outbox-runtime-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_SEGMENTED_OUTBOX_RUNTIME_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_SEGMENTED_OUTBOX_RUNTIME_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_segmented_outbox_runtime_validation.cpp -lcrypto -o build/hub_segmented_outbox_runtime_validation
	./build/hub_segmented_outbox_runtime_validation

GS116_COMMISSIONING_CRYPTO_HOST_TEST_HOST_SOURCES := firmware/common/security/commissioning_protocol.cpp firmware/common/security/commissioning_wire.cpp firmware/common/security/runtime_frame_security.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_COMMISSIONING_CRYPTO_HOST_TEST_HOST_SOURCES))
commissioning-crypto-host-test: build $(call host_objects,$(GS116_COMMISSIONING_CRYPTO_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_COMMISSIONING_CRYPTO_HOST_TEST_HOST_SOURCES)) tests/cpp/commissioning_crypto_validation.cpp -lcrypto -o build/commissioning_crypto_validation
	./build/commissioning_crypto_validation

GS116_REJOIN_HOST_TEST_HOST_SOURCES := firmware/common/security/rejoin_protocol.cpp firmware/common/security/commissioning_wire.cpp firmware/common/security/runtime_frame_security.cpp firmware/common/transport/data_plane_codec.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_REJOIN_HOST_TEST_HOST_SOURCES))
rejoin-host-test: build $(call host_objects,$(GS116_REJOIN_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_REJOIN_HOST_TEST_HOST_SOURCES)) tests/cpp/rejoin_host_validation.cpp -lcrypto -o build/rejoin_host_validation
	./build/rejoin_host_validation

GS116_ASSOCIATION_HOST_TEST_HOST_SOURCES := firmware/common/security/association_persistence.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_ASSOCIATION_HOST_TEST_HOST_SOURCES))
association-host-test: build $(call host_objects,$(GS116_ASSOCIATION_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_ASSOCIATION_HOST_TEST_HOST_SOURCES)) tests/cpp/association_persistence_validation.cpp -lcrypto -o build/association_persistence_validation
	./build/association_persistence_validation

GS116_NODE_RECOVERY_HOST_TEST_HOST_SOURCES := shared/src/logging.cpp firmware/node/components/radio/node_radio.cpp firmware/node/components/storage/node_store.cpp firmware/node/runtime/node_runtime.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_NODE_RECOVERY_HOST_TEST_HOST_SOURCES))
node-recovery-host-test: build $(call host_objects,$(GS116_NODE_RECOVERY_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_NODE_RECOVERY_HOST_TEST_HOST_SOURCES)) tests/cpp/node_runtime_recovery_validation.cpp -o build/node_runtime_recovery_validation
	./build/node_runtime_recovery_validation

GS116_NODE_RECOVERY_PERSISTENCE_HOST_TEST_HOST_SOURCES := shared/src/logging.cpp firmware/common/transport/data_plane_codec.cpp firmware/common/transport/node_retirement_protocol.cpp firmware/node/components/radio/node_radio.cpp firmware/node/components/storage/node_store.cpp firmware/node/runtime/node_runtime.cpp firmware/node/components/storage/node_recovery_persistence.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_NODE_RECOVERY_PERSISTENCE_HOST_TEST_HOST_SOURCES))
node-recovery-persistence-host-test: build $(call host_objects,$(GS116_NODE_RECOVERY_PERSISTENCE_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_NODE_RECOVERY_PERSISTENCE_HOST_TEST_HOST_SOURCES)) tests/cpp/node_recovery_persistence_validation.cpp -lcrypto -o build/node_recovery_persistence_validation
	./build/node_recovery_persistence_validation

GS116_NODE_RETIREMENT_PROTOCOL_HOST_TEST_HOST_SOURCES := shared/src/logging.cpp firmware/common/transport/data_plane_codec.cpp firmware/common/transport/node_retirement_protocol.cpp firmware/common/security/runtime_frame_security.cpp firmware/node/components/radio/node_radio.cpp firmware/node/components/storage/node_store.cpp firmware/node/runtime/node_runtime.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_NODE_RETIREMENT_PROTOCOL_HOST_TEST_HOST_SOURCES))
node-retirement-protocol-host-test: build $(call host_objects,$(GS116_NODE_RETIREMENT_PROTOCOL_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_NODE_RETIREMENT_PROTOCOL_HOST_TEST_HOST_SOURCES)) tests/cpp/node_retirement_protocol_validation.cpp -lcrypto -o build/node_retirement_protocol_validation
	./build/node_retirement_protocol_validation

GS116_HUB_RETIREMENT_SNAPSHOT_HOST_TEST_HOST_SOURCES := firmware/common/transport/data_plane_codec.cpp firmware/common/transport/node_retirement_protocol.cpp firmware/hub/components/storage/durable_transition.cpp firmware/hub/components/storage/node_retirement_snapshot.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_RETIREMENT_SNAPSHOT_HOST_TEST_HOST_SOURCES))
hub-retirement-snapshot-host-test: build $(call host_objects,$(GS116_HUB_RETIREMENT_SNAPSHOT_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(call host_objects,$(GS116_HUB_RETIREMENT_SNAPSHOT_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_retirement_snapshot_validation.cpp -lcrypto -o build/hub_retirement_snapshot_validation
	./build/hub_retirement_snapshot_validation

GS116_SIMULATOR_HOST_SOURCES := host/simulator/main.cpp firmware/hub/components/storage/durable_event_outbox.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_SIMULATOR_HOST_SOURCES))
simulator: build $(CPP_OBJECTS) $(call host_objects,$(GS116_SIMULATOR_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_SIMULATOR_HOST_SOURCES)) -o build/ghar_sajag_simulator
	./build/ghar_sajag_simulator

simulate-matrix:
	python3 tools/sim/scenario_matrix.py

python-test: lab-build hub-backend-commit-host-test
	# unittest discovery includes the Phase 1 foundation, persistence and WSGI API suites.
	PYTHONPATH=backend python3 -m unittest discover -s tests/python -p 'test_*.py' -v

app-test:
	node --test tests/js/*.test.mjs

contracts:
	python3 scripts/verify_contracts.py

verify: contracts cpp-test simulator simulate-matrix python-test app-test product-test

.PHONY: product-test verify-products
GS116_PRODUCT_TEST_HOST_SOURCES := shared/src/logging.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_PRODUCT_TEST_HOST_SOURCES))
product-test: build $(call host_objects,$(GS116_PRODUCT_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) tests/cpp/test_product.cpp $(call host_objects,$(GS116_PRODUCT_TEST_HOST_SOURCES)) -o build/product_tests_$(PRODUCT)
	./build/product_tests_$(PRODUCT)

verify-products:
	$(MAKE) verify PRODUCT=base
	$(MAKE) verify PRODUCT=ai

verify-trace:
	$(MAKE) verify TRACE_FLAGS=-DGS_ENABLE_TRACE=1 GS_TRACE=1

verify-sanitize:
	ASAN_OPTIONS=detect_leaks=0 $(MAKE) cpp-test CXXFLAGS='-std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer'

clean:
	rm -rf build

# T01: local integration adapter; the original component suites remain unchanged.
.PHONY: lab-build lab e2e-test
GS116_LAB_BUILD_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp host/simulator/interactive.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_LAB_BUILD_HOST_SOURCES))
lab-build: build $(CPP_OBJECTS) $(call host_objects,$(GS116_LAB_BUILD_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_LAB_BUILD_HOST_SOURCES)) -o build/ghar_sajag_interactive

lab: lab-build
	python3 tools/sim/local_lab.py

e2e-test: lab-build
	python3 tools/sim/local_lab.py --test

.PHONY: http-e2e-test
http-e2e-test: lab-build
	python3 tests/simulation_http_test.py

# v1.5.4 regression/release validation framework
coverage-test:
	python3 scripts/check_validation_coverage.py

manual-test-plan:
	python3 tools/validation/generate_manual_plan.py

functional-test: lab-build
	python3 tools/validation/run_functional_suite.py

dummy-sensor-test: lab-build
	python3 tools/validation/run_dummy_sensor_streams.py

performance-profile: lab-build
	python3 tools/performance/profile_pwa.py

performance-test: lab-build
	python3 tools/performance/profile_pwa.py
	python3 tools/stress/run_stress.py --profile SMALL

STRESS_PROFILE ?= MEDIUM
stress-test: lab-build
	python3 tools/stress/run_stress.py --profile $(STRESS_PROFILE) --allow-large

# Focused bounded Phase 3B API concurrency/household-isolation qualification.
# Kept separate from performance-test and the normal final release gate.
concurrency-test: lab-build
	python3 tools/stress/run_concurrency.py

# Explicit endurance/soak target; never included in normal validation/release gates.
endurance-test: lab-build
	python3 tools/stress/run_stress.py --profile EXTENDED --allow-large

VALIDATION_REUSE_REPORTS ?=
VALIDATION_RECEIPTS = $(foreach report,$(VALIDATION_REUSE_REPORTS),--reuse-report $(report))
.PHONY: validation-node validation-hub validation-contract validation-backend validation-pwa validation-tooling validation-build validation-sanitize validation-framework-test
validation-node validation-hub validation-contract validation-backend validation-pwa validation-tooling:
	python3 tools/validation/component_gate.py --suite $(patsubst validation-%,%,$@) $(VALIDATION_RECEIPTS)

validation-fast:
	python3 tools/validation/component_gate.py --suite fast $(VALIDATION_RECEIPTS)

validation-build: build $(CPP_OBJECTS) $(CPP_EXTRA_OBJECTS)
	@echo "VALIDATION BUILD PASS"

validation-framework-test:
	PYTHONPATH=backend:. python3 -m unittest discover -s tests/python -p 'test_component_gate.py' -v

validation-sanitize:
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 $(MAKE) cpp-test gs40-host-test CXXFLAGS='-std=c++17 -O1 -g1 -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer'
	@echo "VALIDATION SANITIZERS PASS"

# HW-M1 firmware regression/release gate. Physical acceptance is deliberately
# reported as MANUAL_REQUIRED/PENDING; this target never flashes hardware.
HW_OTA_WARNING_PERCENT ?= 15
hw-validation-fast:
	python3 tools/validation/hw_release_gate.py --fast --ota-warning-percent $(HW_OTA_WARNING_PERCENT)

hw-pair-build:
	python3 scripts/build_hw_pair.py

hw-release-gate:
	python3 tools/validation/hw_release_gate.py --ota-warning-percent $(HW_OTA_WARNING_PERCENT) $(if $(filter 1,$(HIL)),--hil,)

# Connected Hub+C3 Phase-1 HIL. setup discovers and records identities but never
# flashes. smoke/regression own locking, paired HIL build, safe flash caching,
# serial capture, cleanup and fail-closed evidence.
hil-setup:
	python3 tools/hil/phase1.py setup

hil-preflight:
	python3 tools/hil/phase1.py preflight

hil-smoke:
	python3 tools/hil/phase1.py smoke

hil-regression:
	python3 tools/hil/phase1.py regression

hil-qualify:
	python3 tools/hil/qualify.py

hil-checkpoint-smoke:
	python3 tools/hil/qualify.py --checkpoint-smoke

hil-fota:
	python3 tools/hil/phase1.py fota

hil-checkpoint-fota:
	python3 tools/hil/qualify.py --checkpoint-fota

hil-secure-signed-fota:
	python3 tools/hil/secure_signed_fota.py

hil-checkpoint-secure-signed-fota:
	python3 tools/hil/qualify.py --checkpoint-secure-signed-fota

hil-supervisor-test:
	python3 -m unittest tests.python.test_hil_supervisor -v
	python3 -m unittest tests.python.test_secure_signed_fota_fixture -v
	python3 tools/hil/check_usb_helper.py

hil-tooling-test: hil-supervisor-test
	python3 -m unittest tests.python.test_hil_phase1 -v
	python3 -m unittest tests.python.test_hil_real_replay -v
	python3 -m unittest tests.python.test_physical_hil_catalogue -v

# Catalogue/integrity-only: never probes, opens, resets, flashes or commands boards.
physical-hil-catalogue-test:
	python3 tools/validation/physical_hil_catalogue.py --check

hil-host-check:
	python3 tools/validation/hil_host_gate.py --fast
	python3 -m unittest tests.python.test_hw_pair_build -v

hil-target-build-check:
	python3 scripts/build_hil_pair.py

release-gate:
	python3 tools/validation/release_gate.py

release-gate-browser:
	python3 tools/validation/release_gate.py --require-browser

.PHONY: pwa-bridge-test
pwa-bridge-test: lab-build
	python3 tests/pwa_bridge_test.py

.PHONY: pwa-68-api-test pwa-68-frontend-test pwa-68-browser-test pwa-e2e-test
pwa-68-api-test: lab-build
	python3 tests/pwa_68_api_test.py

pwa-68-frontend-test: lab-build
	python3 tests/pwa_68_frontend_test.py

pwa-68-browser-test: lab-build
	python3 tests/pwa_68_browser_test.py

pwa-e2e-test: pwa-bridge-test pwa-68-api-test pwa-68-frontend-test


.PHONY: playwright-install playwright-gate release-gate-browser-mandatory

playwright-install:
	npm install
	npx playwright install --with-deps chromium

playwright-gate:
	python3 scripts/playwright_preflight.py
	# The runner executes every tests/playwright spec for desktop and mobile projects.
	python3 scripts/run_playwright_gate.py

# Final release gate: browser/DOM automation is mandatory.
release-gate-browser-mandatory: release-gate playwright-gate
	@echo "PASS: mandatory Playwright/Chromium PWA browser gate"

.PHONY: release-gate-final
RELEASE_GATE_FINAL_SKIP_PERFORMANCE ?= 0
release-gate-final:
	python3 tools/validation/component_gate.py --suite release $(VALIDATION_RECEIPTS)

validation-nightly:
	python3 tools/validation/nightly.py $(if $(filter 1,$(HIL)),--hil,) $(if $(HIL_SOAK_MINUTES),--hil-soak-minutes $(HIL_SOAK_MINUTES),)

# GCC's built-in gcov data is collected with the repository-provided LCOV.
# This is visibility only: no arbitrary percentage threshold is imposed.
validation-coverage: build
	rm -rf build/coverage evidence/coverage
	mkdir -p build/coverage evidence/coverage
	$(HOST_CXX) -std=c++17 -O0 -g -Wall -Wextra -Werror -pedantic --coverage $(PRODUCT_FLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) tests/cpp/test_main.cpp -o build/coverage/cpp_tests
	$(HOST_CXX) -std=c++17 -O0 -g -Wall -Wextra -Werror -pedantic --coverage $(PRODUCT_FLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) tests/cpp/master_validation.cpp -o build/coverage/master_validation
	$(HOST_CXX) -std=c++17 -O0 -g -Wall -Wextra -Werror -pedantic --coverage $(PRODUCT_FLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) tests/cpp/fota_host_validation.cpp -o build/coverage/fota_host_validation
	./build/coverage/cpp_tests
	./build/coverage/master_validation
	./build/coverage/fota_host_validation
	lcov --capture --directory build/coverage --output-file build/coverage/all.info --rc branch_coverage=1 --ignore-errors mismatch,inconsistent
	lcov --extract build/coverage/all.info '*/firmware/*' '*/shared/*' --output-file evidence/coverage/coverage.info --rc branch_coverage=1 --ignore-errors unused
	genhtml evidence/coverage/coverage.info --output-directory evidence/coverage/html --branch-coverage --quiet
	python3 tools/validation/coverage_report.py

# Production completion coverage shares the real journal/provider migration fixture.
.PHONY: hub-backend-completion-host-test
hub-backend-completion-host-test: hub-journal-migration-host-test

.PHONY: hub-runtime-checkpoint-host-test
GS116_HUB_RUNTIME_CHECKPOINT_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/storage/outbox_journal_backend.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_RUNTIME_CHECKPOINT_HOST_TEST_HOST_SOURCES))
hub-runtime-checkpoint-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_RUNTIME_CHECKPOINT_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_RUNTIME_CHECKPOINT_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_runtime_checkpoint_validation.cpp -lcrypto -o build/hub_runtime_checkpoint_validation
	./build/hub_runtime_checkpoint_validation

.PHONY: hub-identity-compaction-host-test
GS116_HUB_IDENTITY_COMPACTION_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/storage/outbox_journal_backend.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_IDENTITY_COMPACTION_HOST_TEST_HOST_SOURCES))
hub-identity-compaction-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_IDENTITY_COMPACTION_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_IDENTITY_COMPACTION_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_runtime_checkpoint_validation.cpp -lcrypto -o build/hub_identity_compaction_validation
	./build/hub_identity_compaction_validation --identity-generation

.PHONY: hub-incremental-completion-host-test
GS116_HUB_INCREMENTAL_COMPLETION_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/storage/outbox_journal_backend.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_INCREMENTAL_COMPLETION_HOST_TEST_HOST_SOURCES))
hub-incremental-completion-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_INCREMENTAL_COMPLETION_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_INCREMENTAL_COMPLETION_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_runtime_checkpoint_validation.cpp -lcrypto -o build/hub_incremental_completion_validation
	./build/hub_incremental_completion_validation --incremental-completion

MIXED_BODY_TEST_BINARY ?= build/hub_mixed_body_compaction_validation
.PHONY: hub-mixed-body-compaction-host-test
GS116_HUB_MIXED_BODY_COMPACTION_HOST_TEST_HOST_SOURCES := firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/storage/outbox_journal_backend.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_HUB_MIXED_BODY_COMPACTION_HOST_TEST_HOST_SOURCES))
hub-mixed-body-compaction-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_MIXED_BODY_COMPACTION_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_HUB_MIXED_BODY_COMPACTION_HOST_TEST_HOST_SOURCES)) tests/cpp/hub_mixed_body_compaction_validation.cpp -lcrypto -o $(MIXED_BODY_TEST_BINARY)
	$(MIXED_BODY_TEST_BINARY)

P2D_TEST_BINARY ?= build/p2d_cloud_contract_validation
.PHONY: p2d-cloud-contract-host-test
GS116_P2D_CLOUD_CONTRACT_HOST_TEST_HOST_SOURCES := firmware/hub/components/cloud/http_backend_transport.cpp firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/storage/outbox_journal_backend.cpp host/security/openssl_commissioning_crypto.cpp
HOST_TEST_OBJECTS += $(call host_objects,$(GS116_P2D_CLOUD_CONTRACT_HOST_TEST_HOST_SOURCES))
p2d-cloud-contract-host-test: build $(CPP_OBJECTS) $(call host_objects,$(GS116_P2D_CLOUD_CONTRACT_HOST_TEST_HOST_SOURCES))
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(call host_objects,$(GS116_P2D_CLOUD_CONTRACT_HOST_TEST_HOST_SOURCES)) tests/cpp/p2d_cloud_contract_validation.cpp -lcrypto -o $(P2D_TEST_BINARY)
	$(P2D_TEST_BINARY)

P2D_HTTPS_TEST_BINARY ?= build/p2d_https_channel_validation
.PHONY: p2d-https-channel-host-test
p2d-https-channel-host-test: build $(CPP_OBJECTS)
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) -Itests/cpp/p2d_idf_fake $(CPP_OBJECTS) firmware/hub/components/cloud/http_backend_transport.cpp firmware/hub/target/esp32s3/https_backend_channel.cpp firmware/hub/components/storage/durable_event_outbox.cpp firmware/hub/components/storage/outbox_journal_backend.cpp host/security/openssl_commissioning_crypto.cpp tests/cpp/p2d_https_channel_validation.cpp -lcrypto -o $(P2D_HTTPS_TEST_BINARY)
	$(P2D_HTTPS_TEST_BINARY)


# GS-130 permanent production boundary and portable PSA regressions.
.PHONY: feature-boundary-host-test factory-node-reset-host-test
FEATURE_BOUNDARY_OBJECTS := $(call host_objects,firmware/hub/components/storage/durable_event_outbox.cpp)
HOST_TEST_OBJECTS += $(FEATURE_BOUNDARY_OBJECTS)
feature-boundary-host-test: build $(CPP_OBJECTS) $(FEATURE_BOUNDARY_OBJECTS)
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_OBJECTS) $(FEATURE_BOUNDARY_OBJECTS) tests/cpp/feature_boundary_validation.cpp -o build/feature_boundary_validation
	./build/feature_boundary_validation

factory-node-reset-host-test:
	python3 scripts/build_portable_psa_reset.py

.PHONY: feature-coverage-test
feature-coverage-test:
	python3 scripts/check_feature_traceability.py
	PYTHONPATH=backend:. python3 -m unittest discover -s tests/python -p test_feature_traceability.py -v

.PHONY: board-stack-e2e-host-test validation-board-e2e
BOARD_E2E_SOURCES := $(sort $(CPP_SOURCES) $(GS116_MULTINODE_HOST_TEST_HOST_SOURCES) $(GS116_SECURE_FOTA_ADAPTER_HOST_TEST_HOST_SOURCES) firmware/hub/components/storage/outbox_journal_backend.cpp firmware/node/fota/boot_health_gate.cpp)
BOARD_E2E_OBJECTS := $(call host_objects,$(BOARD_E2E_SOURCES))
HOST_TEST_OBJECTS += $(BOARD_E2E_OBJECTS)
board-stack-e2e-host-test: build $(BOARD_E2E_OBJECTS)
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(BOARD_E2E_OBJECTS) tests/cpp/board_stack_e2e_validation.cpp -lcrypto -o build/board_stack_e2e_validation
	./build/board_stack_e2e_validation
validation-board-e2e:
	python3 tools/validation/component_gate.py --suite board-e2e $(VALIDATION_RECEIPTS)

.PHONY: validation-p0-e2e validation-board-hil validation-motion-hil gs130-hil-runner-test p0-product-e2e
P0_BOARD_E2E_SOURCES := $(sort $(CPP_SOURCES) $(GS116_MULTINODE_HOST_TEST_HOST_SOURCES) $(GS116_SECURE_FOTA_ADAPTER_HOST_TEST_HOST_SOURCES) firmware/hub/components/storage/outbox_journal_backend.cpp firmware/node/fota/boot_health_gate.cpp)
P0_BOARD_E2E_OBJECTS := $(call host_objects,$(P0_BOARD_E2E_SOURCES))
HOST_TEST_OBJECTS += $(P0_BOARD_E2E_OBJECTS)
p0-board-stack-event-host-test: build $(P0_BOARD_E2E_OBJECTS) tests/cpp/board_stack_e2e_validation.cpp
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(P0_BOARD_E2E_OBJECTS) tests/cpp/board_stack_e2e_validation.cpp -lcrypto -o build/p0_board_stack_e2e_validation
	./build/p0_board_stack_e2e_validation --emit-p0-event build/p0_product_event.json build/p0_cloud_sync_request.json

p0-product-e2e: p0-board-stack-event-host-test
	PYTHONPATH=backend:. python3 -m unittest tests.python.test_p0_e2e_selection -v
	python3 tools/validation/check_p0_e2e_scenarios.py
	PYTHONPATH=backend:. python3 tests/python/run_full_product_p0_e2e.py --event build/p0_product_event.json --cloud-request build/p0_cloud_sync_request.json --report build/p0_product_e2e_report.json $(if $(strip $(P0_SCENARIOS)),--scenarios=$(P0_SCENARIOS),)

validation-p0-e2e:
	python3 tools/validation/component_gate.py --suite p0-e2e $(VALIDATION_RECEIPTS)

gs130-hil-runner-test:
	PYTHONPATH=tools/hil python3 -m unittest discover -s tools/hil -p test_gs130_runners.py -v

validation-board-hil:
	python3 tools/hil/gs130_board_hil.py $(HIL_ARGS)

validation-motion-hil:
	python3 tools/hil/gs130_motion_hil.py $(HIL_ARGS)

s3-fixture-commissioning-test:
	python3 -m unittest tests.python.test_s3_fixture_commissioning -v
# All cached production objects retain generated-header and source/header dependencies.
$(HOST_TEST_OBJECTS): Makefile build/gs40_generated/gs/node_health_config.hpp
-include $(HOST_TEST_OBJECTS:.o=.d)
