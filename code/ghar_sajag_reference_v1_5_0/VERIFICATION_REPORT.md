# Reference code 1.5.0 verification

- PASS: fresh `make verify-products`; each profile passed 57 C++ checks, 13 Python tests, 8 JavaScript tests, contract checks, simulator/matrix and its product tests. See `evidence/Component_Regression_v1.5.0.txt`.
- PASS: 13 cross-language host integration scenarios. See `evidence/Scenario_Report_v1.5.0.json` and `.txt`.
- PASS: 9 real local HTTP integration checks, including the 13-scenario run, caregiver ownership and offline incident detection timestamps. See `evidence/HTTP_Integration_v1.5.0.txt`.
- PASS: JavaScript syntax check for the new page module and Python compilation for the adapter/tests.
- PASS: comparison of existing domain source against 1.4.2; only product-version metadata changed. New adapter code is additional.
- NOT RUN: actual Playwright/Chromium rendering, clicking and mobile layout test. Browser download timed out in this environment. The optional test script and manual walkthrough are supplied; this is not a visual/browser acceptance claim.

The regression suite preceded the final adapter-only detection-timestamp refinement; all nine HTTP tests and their 13-scenario integration run passed after that refinement. Domain algorithms were not subsequently edited.

A successful connected scenario demonstrates its assertions across the specified adapters. It does not certify all P0 features, durable restart recovery, hardware timing, security, notification delivery or AI interaction. One scenario explicitly records the existing duplicate-reducer evidence defect; it does not mark that defect fixed.
