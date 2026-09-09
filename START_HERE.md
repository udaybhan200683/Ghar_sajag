# Ghar Sajag engineering handover

Documentation edition **2.0**. Reference code **1.4.2**. Immediate scope: **Base Parivar Saathi P0**.

Start with `docs/design/Ghar_Sajag_Engineer_Handover_Guide_v2.0.docx`, then follow its reading order. All seven uploaded Word baselines are expanded, with original headings, tables and figures retained. `reference_baselines` contains the exact uploads for comparison. Historical hypotheses remain identified as such.

## Folders

- `docs/requirements`: SRD and detailed P0 design.
- `docs/design`: architecture, low-level design, sequence guide, AI design and handover guide.
- `docs/hardware`: deployment guide and updated BOM workbook with qualification notes.
- `docs/product`: product/pilot blueprint.
- `docs/progress`: tracker, requirement/source mapping, open work and preservation report.
- `diagrams/sequences/png`: standalone sequence images.
- `diagrams/sequences/uml`: editable PlantUML sequence sources.
- `diagrams/modules`: module PNGs and UML sources.
- `diagrams/architecture`: whole-system diagram sources/images.
- `code/ghar_sajag_reference_v1_4_2`: complete annotated reference source.
- `evidence`: command transcripts and package validation.

Run `make verify PRODUCT=base` inside the code directory in Ubuntu. This is a host build, not an ESP-IDF firmware flashing project. Use `make verify-products` for shared-core changes. Source version 1.4.2 adds comments and version metadata; it does not implement new behaviour. AI session management is retained; speech, model integration and hardware tests are pending.

Read `progress.txt` before assigning work. A source comment `@requirements F05, E02` links responsibilities; it does not mean those requirements have full acceptance coverage. Keep requirement IDs stable and update code, tests, diagrams and status together when behaviour changes.

Extract to a short Windows path such as `F:\GS`. Preserve your existing repository and copy this package into a new review folder before replacing older files. No Git commit or website deployment has been made by this documentation task.
