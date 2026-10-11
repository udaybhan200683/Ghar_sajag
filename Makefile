PRODUCT_DIR := code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2

.PHONY: validation-node validation-hub validation-contract validation-backend validation-pwa validation-tooling validation-framework-test
validation-node validation-hub validation-contract validation-backend validation-pwa validation-tooling validation-framework-test:
	$(MAKE) -C $(PRODUCT_DIR) $@

.PHONY: validation-fast release-gate-final hw-pair-build hw-release-gate validation-nightly hil-setup hil-preflight hil-smoke hil-regression hil-qualify hil-checkpoint-smoke hil-fota hil-secure-signed-fota hil-checkpoint-fota hil-checkpoint-secure-signed-fota hil-supervisor-test hil-tooling-test hil-host-check hil-target-build-check
validation-fast release-gate-final hw-pair-build hw-release-gate validation-nightly hil-setup hil-preflight hil-smoke hil-regression hil-qualify hil-checkpoint-smoke hil-fota hil-secure-signed-fota hil-checkpoint-fota hil-checkpoint-secure-signed-fota hil-supervisor-test hil-tooling-test hil-host-check hil-target-build-check:
	$(MAKE) -C $(PRODUCT_DIR) $@

.PHONY: validation-board-e2e feature-coverage-test physical-hil-catalogue-test
validation-board-e2e feature-coverage-test physical-hil-catalogue-test:
	$(MAKE) -C $(PRODUCT_DIR) $@

.PHONY: validation-p0-e2e validation-board-hil validation-motion-hil
validation-p0-e2e validation-board-hil validation-motion-hil:
	$(MAKE) -C $(PRODUCT_DIR) $@
