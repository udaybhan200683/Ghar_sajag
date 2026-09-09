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

.PHONY: all verify cpp-test simulator simulate-matrix python-test app-test contracts clean

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

python-test:
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
