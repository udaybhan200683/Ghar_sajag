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
INCLUDES := -I. -Ishared/include -Ifirmware/node/components -Ifirmware/hub/components -Ifirmware/common/security

CPP_SOURCES := \
	shared/src/rules.cpp \
	shared/src/logging.cpp \
	host/logging/file_log_sink.cpp \
	firmware/common/transport/data_plane_codec.cpp \
	firmware/common/transport/session_id.cpp \
	firmware/node/components/sensing/sensing.cpp \
	firmware/node/components/radio/node_radio.cpp \
	firmware/node/components/power/power.cpp \
	firmware/node/components/lifecycle/lifecycle.cpp \
	firmware/node/components/storage/node_store.cpp \
	firmware/node/fota/fota_receiver.cpp \
	firmware/node/runtime/node_runtime.cpp \
	firmware/hub/components/ingest/ingest.cpp \
	firmware/hub/components/storage/journal.cpp \
	firmware/hub/components/time/clock.cpp \
	firmware/hub/components/coverage/coverage.cpp \
	firmware/hub/components/rules/routine_service.cpp \
	firmware/hub/components/ui/resident_ui.cpp \
	firmware/hub/components/lifecycle/config_service.cpp \
	firmware/hub/components/cloud/cloud_sync.cpp \
	firmware/hub/runtime/hub_runtime.cpp \
	firmware/common/security/security.cpp

.PHONY: all verify cpp-test master-validation master-validation-self-test fota-host-test multinode-host-test simulator simulate-matrix python-test app-test contracts clean validation-fast release-gate release-gate-browser manual-test-plan functional-test dummy-sensor-test coverage-test performance-profile performance-test stress-test concurrency-test endurance-test hw-validation-fast hw-pair-build hw-release-gate validation-nightly validation-coverage hil-setup hil-preflight hil-smoke hil-regression hil-qualify hil-supervisor-test hil-tooling-test hil-host-check hil-target-build-check

all: verify

build:
	mkdir -p build logs

cpp-test: build
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) tests/cpp/test_main.cpp -o build/cpp_tests
	./build/cpp_tests

master-validation: build
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) tests/cpp/master_validation.cpp -o build/master_validation
	python3 tools/validation/master_validation.py

master-validation-self-test: build
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) tests/cpp/master_validation.cpp -o build/master_validation
	python3 tools/validation/master_validation.py --self-test

fota-host-test: build
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) tests/cpp/fota_host_validation.cpp -o build/fota_host_validation
	./build/fota_host_validation

multinode-host-test: build
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) host/multinode/scheduled_harness.cpp tests/cpp/multinode_host_validation.cpp -o build/multinode_host_validation
	./build/multinode_host_validation

simulator: build
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) host/simulator/main.cpp -o build/ghar_sajag_simulator
	./build/ghar_sajag_simulator

simulate-matrix:
	python3 tools/sim/scenario_matrix.py

python-test: lab-build
	# unittest discovery includes the Phase 1 foundation, persistence and WSGI API suites.
	PYTHONPATH=backend python3 -m unittest discover -s tests/python -p 'test_*.py' -v

app-test:
	node --test tests/js/*.test.mjs

contracts:
	python3 scripts/verify_contracts.py

verify: contracts cpp-test simulator simulate-matrix python-test app-test product-test

.PHONY: product-test verify-products
product-test: build
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) tests/cpp/test_product.cpp shared/src/logging.cpp -o build/product_tests_$(PRODUCT)
	./build/product_tests_$(PRODUCT)

verify-products:
	$(MAKE) verify PRODUCT=base
	$(MAKE) verify PRODUCT=ai

verify-trace:
	$(MAKE) clean
	$(MAKE) verify TRACE_FLAGS=-DGS_ENABLE_TRACE=1 GS_TRACE=1

verify-sanitize:
	$(MAKE) clean
	ASAN_OPTIONS=detect_leaks=0 $(MAKE) cpp-test CXXFLAGS='-std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer'

clean:
	rm -rf build

# T01: local integration adapter; the original component suites remain unchanged.
.PHONY: lab-build lab e2e-test
lab-build: build
	$(HOST_CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) host/simulator/interactive.cpp -o build/ghar_sajag_interactive

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

validation-fast: hil-tooling-test hil-host-check multinode-host-test
	python3 tools/validation/release_gate.py --quick

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

hil-supervisor-test:
	python3 -m unittest tests.python.test_hil_supervisor -v
	python3 tools/hil/check_usb_helper.py

hil-tooling-test: hil-supervisor-test
	python3 -m unittest tests.python.test_hil_phase1 -v
	python3 -m unittest tests.python.test_hil_real_replay -v

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
release-gate-final: hil-tooling-test hil-host-check hil-target-build-check release-gate-browser-mandatory $(if $(filter 1,$(RELEASE_GATE_FINAL_SKIP_PERFORMANCE)),,performance-test)

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
