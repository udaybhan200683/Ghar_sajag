# Parivar Sathi v3.4.0 — Battery usage analytics and runtime prediction

Implemented:

- Node-side C++ energy-counter model and calibrated mAh/runtime estimator.
- Backend battery analytics service with non-linear voltage→SOC, historical mAh/day, confidence, counter-reset handling and high-drain detection.
- SQL persistence schema for device power profiles and battery usage history.
- Optional node protocol `power` counters in both the JSON contract and C++ `NodeMessage`; the hub retains the latest accepted telemetry per node.
- PWA Device Health/Devices display for %, mV, estimated time left, mAh/day, confidence, wakeups/day, RF retries/day and drain status.
- Household-configurable low-battery alert threshold under Device Schedules.
- High-drain and low-battery conditions remain device-health only and do not change the family care banner.
- Canonical functional catalog expanded from 85 to 92 cases.
- Manual plan regenerated from the same 92-case catalog.
- Browser checks extended for battery prediction, high-drain behavior and configurable alert threshold.

Hardware boundary: current values in the host lab are synthetic calibration inputs. Real-board current/voltage/capacity calibration remains mandatory before runtime estimates are treated as field-accurate.
