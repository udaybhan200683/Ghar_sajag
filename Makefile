PRODUCT_DIR := code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2

.PHONY: validation-fast release-gate-final hw-pair-build hw-release-gate validation-nightly hil-setup hil-preflight hil-smoke hil-regression hil-qualify hil-supervisor-test hil-tooling-test hil-host-check hil-target-build-check
validation-fast release-gate-final hw-pair-build hw-release-gate validation-nightly hil-setup hil-preflight hil-smoke hil-regression hil-qualify hil-supervisor-test hil-tooling-test hil-host-check hil-target-build-check:
	$(MAKE) -C $(PRODUCT_DIR) $@
