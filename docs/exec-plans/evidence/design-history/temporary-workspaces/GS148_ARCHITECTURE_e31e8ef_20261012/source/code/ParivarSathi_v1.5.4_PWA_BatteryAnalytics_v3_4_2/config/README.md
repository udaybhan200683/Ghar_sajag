# GS-40 firmware NodeHealth configuration

Authority: GS-D031 / GS-40. This is the narrow build/startup policy, not GS-128
runtime configuration. No board operation is performed by these tools.

## Input and effective policy

Edit `node_health.json`. Schema 1 has exactly one adjustable timing value:
`node_health.heartbeat_interval_seconds`, default **300**. Piggyback must be
`true`. The internal rule is **3 × interval + 10** seconds, default **910**.
No offline timeout, multiplier, grace or day/night knob is accepted.

Range **15–3600 seconds** reuses the existing portable Node lifecycle validation
(`firmware/node/components/lifecycle/lifecycle.cpp`). It bounds milliseconds and
lease arithmetic well below overflow. This is a software-supported range, not
an RF/power-qualified range. Larger values do not change GS-150's existing
430-second authenticated Hub-contact recovery deadline: necessary security
rejoin may occur before a long heartbeat becomes due and successful rejoin
can defer health. Boot/FOTA/diagnostic exceptions remain unchanged.

The strict Python validator rejects missing/unknown/duplicate keys, invalid
JSON, noninteger/bool/zero/negative/overflow interval, unsupported versions,
piggyback disabled and malformed identities/profiles. The JSON Schema is also
provided. Missing/invalid JSON **fails build or backend startup**; it never
produces health-disabled firmware. Existing installed firmware continues its
previous embedded policy until an authorized update. The generated C++ policy
has a compile-time range/formula assertion and no mutable startup parse, NVS
configuration writes or new partition. Firmware initializes the owner cadence
and Hub profile leases from this representation before servicing communication.

## Mixed deployment

`deployment_profiles` is trusted engineering deployment metadata keyed by the
existing authenticated physical `c3-<12 lowercase MAC hex digits>` identity:

| Selector | Effective heartbeat | Offline lease |
|---|---:|---:|
| `configured` | Single JSON interval | 3 × interval + 10 |
| `legacy_60` | Historical 60 s | 190 s |
| `legacy_120` | Actual preceding BAT-C5 120 s | Historical 310 s |
| Unlisted | Unknown | Unknown; cannot prove healthy coverage |

A **new configured 120 s** policy derives 370 s; `legacy_120` preserves the
actually deployed old 310 s contract. These selectors are versioned compatibility
profiles, not extra numeric timing knobs. Do not infer the policy from health
schema 2, a MAC callback or event occurrence time. No wire or storage format is
changed. The checked-in identity is the known pair's **candidate build** mapping;
this does not claim the protected board was upgraded.

Before staged deployment, record actual old physical identities/profiles. Build
and install the compatible Hub/backend profile map before installing a slower
Node. A transitional configured lease on that Node is conservative during the
short approved paired update; unrelated legacy Nodes keep explicit old profiles.
Verify startup fingerprint and actual applied Node image, then record accepted
mapping. Updating arbitrary deployed Nodes without this map is unsupported;
unlisted identities remain unknown, not silently 910 s. Backend service must
receive the same trusted JSON or `DeploymentPolicy` at startup. The simulator
explicitly labels its logical/provisioned fixtures with the candidate profile;
it does not authenticate a physical deployment or infer one from old firmware text.

## Generate, build and package

From the application root:

```sh
make gs40-config-test gs40-host-test
python3 scripts/generate_node_health_config.py --output build/gs40_generated/gs/node_health_config.hpp
```

C3 and shared S3 Hub CMake call this generator on configure, track JSON/validator
changes and compile its typed policy and SHA-256 into the binary. Changing JSON
therefore requires **rebuilding and separately authorized updating the affected
firmware**, not copying a JSON file beside an old `.bin`. The firmware logs
`GS40 config=<sha256> heartbeat=<seconds> offline=<seconds>` at owner startup.
Legacy raw HIL remains its explicit 60 s historical profile; qualification wake
uses the production configured interval.

Software-only ESP-IDF v6.0.3 example (external generated directories; no flash):

```sh
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
idf.py -C firmware/node/target/esp32c3/idf -B /var/tmp/gs40-c3-build \
  -D SDKCONFIG=/var/tmp/gs40-c3-sdkconfig -D IDF_TARGET=esp32c3 build size
mkdir -p /var/tmp/gs40-assets
cp /var/tmp/gs40-c3-build/gs_hw_m1_node.bin /var/tmp/gs40-assets/node_firmware.bin
idf.py -C firmware/hub/target/esp32s3/idf -B /var/tmp/gs40-s3-build \
  -D SDKCONFIG=/var/tmp/gs40-s3-sdkconfig -D IDF_TARGET=esp32s3 \
  -D GS_NODE_FIRMWARE_ASSET=/var/tmp/gs40-assets/node_firmware.bin build size
python3 scripts/package_node_health_firmware.py \
  --c3-build /var/tmp/gs40-c3-build --s3-build /var/tmp/gs40-s3-build
```

`GS_NODE_HEALTH_CONFIG` may select another validated JSON input in both target
builds; use that exact input for backend startup and packaging. The Hub asset
option preserves the original ignored asset and requires basename
`node_firmware.bin` for existing linker symbols. Packaging rejects mismatched
configuration fingerprints or a Hub containing a different C3 image. The bundle
contains validated JSON/schema, SHA-256 manifest, and each IDF build's existing
bootloader/partition/OTA/app artifacts with existing flash offsets. It does not
change partitions, sign images, authorize deployment or operate hardware.
Use the existing authorized fixture/deployment and signed FOTA workflows;
building this unsigned development bundle is not production qualification.

## Behavioral and measurement limits

Authenticated event reception refreshes Hub contact; matching authenticated
application ACK refreshes the Node cadence. Due event telemetry uses the existing
optional power carrier; if it exceeds frame capacity it is omitted so the event
still transmits. Full sensor/error NodeHealth remains standalone, not a new packet
extension. A failed send schedules the next bounded attempt without changing
`last_authenticated_contact_ms`; MAC success never supplies an application ACK.

GS-150's 10-second best-effort receive budget, confirmed-outage retained sleep,
20 ms awake poll, retry/rejoin deadlines, 30 s sleep cap, GPIO4 safeguards,
32-event limit, persistence and signed FOTA stay intact. Models account for logical
activity only; radio/flash transition current and mAh are unmeasured. Optional
power counters are engineering diagnostics, not calibrated battery telemetry.

Backend freshness is refreshed from received contact evidence, not PWA render
time or retained event occurrence time; unchanged renders do not write health
records. The host bridge passes its explicit modeled received-contact timestamp.

Per-Node monotonic liveness is distinct from Hub cloud lease (190 s), activity
age and Internet state. Per-Node epoch coverage uses that profile's contact
lease when trusted received time is available. No wall clock or full historical
coverage is invented: the secure target still has the documented trusted-epoch
and production cloud-contract limitations. Backend/PWA compatibility is host
validated; actual final-image caregiver visibility remains GS-40 acceptance.
