CXX ?= g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra -Werror -pedantic
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

.PHONY: all verify cpp-test simulator simulate-matrix python-test app-test contracts clean validation-fast release-gate release-gate-browser manual-test-plan functional-test dummy-sensor-test coverage-test performance-profile performance-test stress-test concurrency-test endurance-test

all: verify

build:
	mkdir -p build logs

cpp-test: build
	$(CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) tests/cpp/test_main.cpp -o build/cpp_tests
	./build/cpp_tests

simulator: build
	$(CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) host/simulator/main.cpp -o build/ghar_sajag_simulator
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
	$(CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) tests/cpp/test_product.cpp shared/src/logging.cpp -o build/product_tests_$(PRODUCT)
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
	$(CXX) $(CXXFLAGS) $(TRACE_FLAGS) $(INCLUDES) $(CPP_SOURCES) host/simulator/interactive.cpp -o build/ghar_sajag_interactive

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

validation-fast:
	python3 tools/validation/release_gate.py --quick

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
release-gate-final: release-gate-browser-mandatory performance-test
