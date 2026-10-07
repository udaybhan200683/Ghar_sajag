# Context density experiments

Host only. Neither codec nor mock sector is in production source lists. Run
`make storage-density-host-test storage-density-benchmark`, then
`python3 host/storage/cold_probe.py`. The latter probes Python/zlib on twelve
independent 32-record fixture blocks; it does not add a firmware compressor.

Six immutable context entries, independently serialized at each segment, are
the only dependency of a contextual record. No previously decoded event is
needed. Dictionary misses and arithmetic overflow use absolute escapes.
All current numeric fields survive roundtrip. Presence bits compare against
immutable context, never against mutable previous-event state. Relations mode
uses exact second-unit deltas only when divisible, and omits receive time only
when its offset from occurrence equals the stored context's exact offset.

Varints reject overlong/overflow forms, signed values use defined ZigZag, and
failed decoders leave output unchanged. Raw codecs are not authenticated.
CRC/mock commit markers model accidental tears only. Host AES-GCM experiments
test context/position binding with a synthetic key; real target nonce ranges,
key domains, flash operations, authenticated roots and anti-rollback inventory
are not implemented. A raw decode under a wrong context can produce different
values; callers must authenticate the context and envelope before decoding.

Sector recovery requires externally selected count/extent/serial/epoch/domain.
The fault model cannot establish how that authority is durably published.
GC/COW tests preserve old source until a complete destination exists, but do
not model NVS/ESP32 erase behavior. Lifetime fixture releases all owners
explicitly, retains at most192 keys, and periodically reconstructs the index;
it does not prove retirement-report progress or product overflow policy.

All hot portable buffers/collections are fixed. Million-event C++ new count
is zero. OpenSSL/Python internals allocate outside that measurement. Host
fixture arrays are placed on host stack for convenience; eventual target
workspaces must be static/owner-owned. Timings exclude AES/flash and are not
ESP32 cycles. Current-code ledger uses actual production codecs with empty
reducer/no retirement reports and counts logical blob writes, not physical
NVS amplification. Derived device/daily effects and sensor hardware are not
claimed physically qualified by synthetic event fixtures.

Full-source sizing is separately proposed: independent context overhead is
728 bytes with sample names/config and1,370 bytes with maximum names/config.
The numeric codec does not implement these string/config serializers. Their
cost is charged in trace packing; confidential fields must stay encrypted.
Uniform numerical medians are not a production retention guarantee. Sample
names plus20 ms timing variation need all128 KiB for the synthetic72-hour
NORMAL comparison; maximum names need132 KiB under the conditional reserve
ledger. No72-hour product guarantee or partition enlargement is approved.

For closeout-only one-day source distribution calculations, use the existing
benchmark executable with `--closeout-sizing`. This skips expensive CPU/lifetime
runs, reuses the same codec, and roundtrips every measured source input. It
reports numeric-only, sample-name and maximum-name context costs both with and
without timing variation. Daily records are included in the separate CAPACITY
results, not these one-day DISTRIBUTION/WARM medians.
