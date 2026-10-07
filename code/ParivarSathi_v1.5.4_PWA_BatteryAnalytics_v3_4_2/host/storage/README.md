# Experimental storage efficiency primitives

`efficient_core.hpp` is portable, host-tested code, excluded from all production
source lists. It provides a fixed-capacity exact-key cache, a versioned lossless
numeric Node-event codec, bounded record cursor and exact integer moments.

Run `make storage-efficiency-host-test` and `make storage-efficiency-benchmark`
from the code project. The test processes 1,000,000 events with a fixed 192-record
fixture, periodically reconstructs the index, and instruments C++ allocations.
It also exercises 192/384/416 index limits, forced hash collisions and wraparound
probe chains, random insertion/deletion, signed numeric boundaries, malformed
frames, single-bit corruption, deterministic fuzz inputs and statistic overflow.

CRC is not authentication. These frames are not the deployed persistent format,
and the record cursor is not a flash recovery/reclamation implementation. The
index returning a matching key is not enough for a durable duplicate ACK: a
future owner must authenticate storage, validate enrollment/assignment mapping,
and compare the immutable Node-origin payload or its full authenticated digest.
The prototype never allocates/advances event session/sequence identifiers.
Counters/IDs must not wrap in a future allocator. Index handles are relocatable
cache references, not durable identities.

Moments uses bounded unsigned 16-bit samples; wider/time-of-day inputs need an
explicit domain conversion. Updates use no floating point; descriptive mean and
variance use double only when queried. Variance subtraction can lose precision
at very small deviations around a large mean. No learned anomaly threshold,
decay/rolling policy or product model is implemented. Construct from default
state or the validated decoder, not unchecked external field assignments.

The benchmarks compare lookup candidates and the current **volatile** journal
with a compact CRC-frame/index fixture; neither path measures physical flash
durability. Proposed lookup alone does not measure full duplicate validation.
Checkpoint timing is a 7,168-byte statistics fixture, not a complete production
reducer snapshot. No ESP32 cycles or production performance acceptance is claimed.

See the repository-root
`docs/exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md` efficiency section for
proposed authenticated record sizes, RAM/flash budgets and integration STOP gates.
