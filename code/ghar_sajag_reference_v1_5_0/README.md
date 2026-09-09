# Ghar Sajag reference code 1.5.0

Start with [SIMULATION_START_HERE.md](SIMULATION_START_HERE.md). It gives Ubuntu/WSL setup, commands, expected results, manual scenarios and troubleshooting.

Immediate product: **Base / Parivar Saathi P0**. This release adds a local simulation adapter and connected engineering dashboard to reference code 1.4.2. Existing domain algorithms remain unchanged. It is not a flashable ESP-IDF application.

```bash
make verify PRODUCT=base
make e2e-test PRODUCT=base
make http-e2e-test PRODUCT=base
make lab PRODUCT=base
```

Open http://localhost:8765 on your computer after the last command. Ctrl+C stops the lab. Do not run the clean/build matrix concurrently with lab build commands.

The lab connects simulated inputs through real C++ node/hub components, the Python backend and existing app view/action helpers. Radio, clock and notification provider are substituted; storage remains in memory. It covers selected connected flows, not every P0 requirement. AI remains a fake-provider/controller seam tested separately by `make verify-products`.

See [the adapter LLD](docs/SIMULATION_LLD_v1.0.md), [verification evidence](VERIFICATION_REPORT.md) and [progress](progress.txt). Retain your separate documentation v2.0 package; its nine Word documents and BOM are not duplicated here. Its baseline open-work and requirement mappings are copied under `docs/reference_v2/` for convenience.
