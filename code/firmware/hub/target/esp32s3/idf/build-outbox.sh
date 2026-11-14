#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../../../../../../" && pwd)"

usage() {
    echo "Usage: $0 [engineering|release]" >&2
    echo "Default profile: engineering (registered GS40 TEST_ONLY serial fixture)." >&2
}

if (( $# > 1 )); then
    usage
    exit 2
fi
profile="${1:-engineering}"
case "$profile" in
    engineering|release) ;;
    *)
        echo "Unsupported S3 build profile '$profile'; only engineering or release is accepted. Partition layouts cannot be selected as profiles." >&2
        usage
        exit 2
        ;;
esac

if [[ "$profile" == "release" && -n "${GS40_TEST_ONLY_CONFIG_ROOT_DER:-}" ]]; then
    echo "Release profile rejects GS40 TEST_ONLY config-root input." >&2
    exit 2
fi

fixture_root="${XDG_CONFIG_HOME:-$HOME/.config}/ghar-sajag/gs117-tc001"
fixture_json="$fixture_root/fixture.json"
canonical_config_root="$fixture_root/config-root-public.der"
fixture_state="${XDG_STATE_HOME:-$HOME/.local/state}/ghar-sajag/gs117-tc001"
asset_override="${GS_NODE_FIRMWARE_ASSET:-}"
config_root_override="${GS40_TEST_ONLY_CONFIG_ROOT_DER:-}"

# Resolve the current Engineering pair from the established fixture record and
# its verified installed-app artifact. Release input must come from an
# existing production pairing report; this script never builds/re-generates C3.
resolved_inputs="$(python3 - "$profile" "$fixture_json" "$canonical_config_root" \
    "$config_root_override" "$asset_override" "$fixture_state" <<'PY'
import hashlib
import json
import pathlib
import re
import sys

profile, fixture_path, canonical_root_path, root_override, asset_override, state_root = sys.argv[1:]

def fail(message):
    print(f"build-outbox: {message}", file=sys.stderr)
    raise SystemExit(2)

def fixture_control_transport(fixture):
    board = fixture.get("s3", {})
    if board.get("port") != "COM10" or board.get("serial_number") != "E0:72:A1:D3:8D:34":
        fail("registered S3 control endpoint identity is incompatible")
    descriptor = str(board.get("usb_hwid", ""))
    if descriptor.startswith("USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34 "):
        return "usb_serial_jtag"
    if descriptor.startswith("USB VID:PID=1A86:55D3 "):
        return "uart0"
    fail("registered S3 USB descriptor has no supported GS40 control transport")

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

if profile == "engineering":
    fixture_file = pathlib.Path(fixture_path)
    root_file = pathlib.Path(canonical_root_path)
    if not fixture_file.is_file():
        fail(f"registered Engineering fixture is missing: {fixture_file}")
    if not root_file.is_file() or root_file.stat().st_size == 0:
        fail(f"canonical GS40 public config-root DER is missing: {root_file}")
    try:
        fixture = json.loads(fixture_file.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"registered Engineering fixture cannot be read: {error}")
    if (fixture.get("schema_version") != 1 or fixture.get("test_id") != "TC-001" or
            fixture.get("profile") != "GS179_TEST_ONLY" or
            fixture.get("qualification_profile") != "GS117_DEV_TEST_ONLY" or
            fixture.get("home_id") != "gs177-test-product" or
            fixture.get("hub_id") != "hub-e072a1d38d34" or
            fixture.get("physical_device_id") != "c3-146393c5d158"):
        fail("registered fixture identity/profile is not the expected GS-117 TEST_ONLY pair")
    expected_c3 = str(fixture.get("c3", {}).get("image_sha256", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_c3):
        fail("registered fixture does not pin a valid C3 image SHA-256")

    root = root_file.resolve()
    if root_override:
        override = pathlib.Path(root_override)
        if not override.is_file() or digest(override) != digest(root_file):
            fail("GS40 config-root override does not match the canonical fixture public DER")
        root = override.resolve()

    if asset_override:
        asset = pathlib.Path(asset_override)
        if not asset.is_file():
            fail("GS_NODE_FIRMWARE_ASSET does not name an existing C3 application image")
        asset = asset.resolve()
    else:
        state = pathlib.Path(state_root)
        candidates = sorted(
            path for path in state.rglob("c3-current-app.bin")
            if path.is_file() and path.parent.name == "trusted-artifacts" and
            path.parent.parent.name.startswith("provenance-refresh-")
        ) if state.is_dir() else []
        matches = [path for path in candidates if digest(path) == expected_c3]
        if len(matches) != 1:
            fail(f"fixture-pinned C3 asset resolution requires one exact match; found {len(matches)}")
        asset = matches[0].resolve()

    if digest(asset) != expected_c3:
        fail("C3 asset SHA-256 does not match the registered GS-117 fixture")
    print(root)
    print(asset)
    print(expected_c3)
    print(fixture_control_transport(fixture))
else:
    if not asset_override:
        fail("release profile requires GS_NODE_FIRMWARE_ASSET for an existing production C3 pair")
    asset = pathlib.Path(asset_override)
    if not asset.is_file():
        fail("GS_NODE_FIRMWARE_ASSET does not name an existing C3 application image")
    asset = asset.resolve()
    if asset.parent.name != "assets":
        fail("release C3 asset must be selected from an existing paired build's assets directory")
    report_path = asset.parent.parent / "report.json"
    if not report_path.is_file():
        fail("release C3 asset is missing its existing paired build report")
    try:
        report = json.loads(report_path.read_text())
        build_profile = str(report.get("profile", ""))
        image_record = report.get("images", {}).get("c3", {})
    except (OSError, json.JSONDecodeError) as error:
        fail(f"release C3 pair report cannot be read: {error}")
    required_off = ("GS40_TEST_ONLY_CLOUDSYNC=OFF", "GS_HIL_BUILD=OFF",
                    "GS_HIL_CONTROL=OFF", "GS_HIL_COMMISSIONING=OFF")
    if (not build_profile.startswith("production ") or
            any(item not in build_profile for item in required_off) or
            report.get("test_only_pathways") != "VERIFIED_DISABLED"):
        fail("release C3 pair report is not a production profile with TEST_ONLY pathways disabled")
    actual_sha = digest(asset)
    if image_record.get("sha256") != actual_sha:
        fail("release C3 asset SHA-256 does not match its existing pair report")
    print("NONE")
    print(asset)
    print(actual_sha)
    print("release")
PY
)" || exit $?
mapfile -t resolved <<< "$resolved_inputs"
if (( ${#resolved[@]} != 4 )); then
    echo "Unable to resolve the S3 build inputs." >&2
    exit 2
fi
config_root="${resolved[0]}"
node_asset="${resolved[1]}"
node_asset_sha="${resolved[2]}"
control_transport="${resolved[3]}"

if [[ "$profile" == "engineering" ]]; then
    if ! openssl pkey -pubin -inform DER -in "$config_root" -noout >/dev/null 2>&1; then
        echo "Canonical GS40 config-root input is not a valid DER public key." >&2
        exit 2
    fi
fi

if [[ -z "${IDF_PATH:-}" ]]; then
    IDF_PATH="/home/udaybhan/.espressif/v6.0.3/esp-idf"
fi
if [[ ! -f "$IDF_PATH/export.sh" ]]; then
    echo "ESP-IDF export.sh not found at $IDF_PATH" >&2
    exit 2
fi

# Every run gets its own profile-specific sdkconfig and build tree. Existing
# artifacts are preserved, while a prior SDK configuration cannot leak across
# Engineering and Release builds.
build_base="${GS_S3_OUTBOX_BUILD_ROOT:-/home/udaybhan/projects/.ghar_sajag_s3_outbox_lifecycle_build}"
build_base="$(mkdir -p -- "$build_base" && cd -- "$build_base" && pwd -P)"
case "$build_base/" in
    "$script_dir/"*)
        echo "Build root must remain outside the S3 source tree." >&2
        exit 2
        ;;
esac
build_parent="$build_base/$profile"
mkdir -p -- "$build_parent"
run_stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
build_root="$(mktemp -d "$build_parent/$run_stamp-XXXXXX")"
build_dir="$build_root/build"
mkdir -p -- "$build_dir" "$build_root/assets"
staged_node_asset="$build_root/assets/node_firmware.bin"
cp -- "$node_asset" "$staged_node_asset"
if [[ "$(sha256sum "$staged_node_asset" | cut -d ' ' -f 1)" != "$node_asset_sha" ]]; then
    echo "Staged C3 asset hash changed during build preparation." >&2
    exit 2
fi

export GS_NODE_FIRMWARE_ASSET="$staged_node_asset"
export SDKCONFIG="$build_root/sdkconfig"
defaults=("$script_dir/sdkconfig.defaults" "$script_dir/sdkconfig.defaults.outbox")
cmake_args=(
    -D IDF_TARGET=esp32s3
    -D "SDKCONFIG=$SDKCONFIG"
    -D GS_S3_DIAGNOSTIC_ONLY=OFF
    -D GS68_CLOUDSYNC_DIAGNOSTIC_ONLY=OFF
    -D GS_HIL_BUILD=OFF
    -D GS_HIL_CONTROL=OFF
    -D GS_HIL_COMMISSIONING=OFF
    -D GS_HIL_C8_ACK_DROP=OFF
    -D GS_HIL_C8_ACK_HOLD=OFF
    -D GS_HIL_SIGNED_FOTA=OFF
    -D "GS_NODE_FIRMWARE_ASSET=$staged_node_asset"
)

if [[ "$profile" == "engineering" ]]; then
    defaults+=("$script_dir/sdkconfig.gs40_test_only.defaults")
    if [[ "$control_transport" == "uart0" ]]; then
        defaults+=("$script_dir/sdkconfig.gs40_test_only_uart.defaults")
    fi
    cmake_args+=(
        -D GS40_TEST_ONLY_CLOUDSYNC=ON
        -D "GS40_TEST_ONLY_CONFIG_ROOT_DER=$config_root"
    )
else
    cmake_args+=(
        -D GS40_TEST_ONLY_CLOUDSYNC=OFF
        -D GS40_TEST_ONLY_CONFIG_ROOT_DER=
    )
fi

defaults_joined="$(IFS=';'; echo "${defaults[*]}")"
export SDKCONFIG_DEFAULTS="$defaults_joined"
cmake_args+=( -D "SDKCONFIG_DEFAULTS=$defaults_joined" )

short_head="$(git -C "$repo_root" rev-parse --short=8 HEAD 2>/dev/null || echo local)"
if [[ -n "${GS_S3_OUTBOX_PROJECT_VER:-}" ]]; then
    project_version="$GS_S3_OUTBOX_PROJECT_VER"
else
    project_version="gs40-renewal-${short_head}-outbox-${profile}-$(date -u +%Y%m%dT%H%M%S)"
fi
if [[ ! "$project_version" =~ ^[A-Za-z0-9._+-]{1,64}$ ]]; then
    echo "Project version contains unsupported characters or exceeds 64 characters." >&2
    exit 2
fi
cmake_args+=( -D "PROJECT_VER=$project_version" )

echo "S3_BUILD_PROFILE=$profile"
echo "S3_CONTROL_TRANSPORT=$control_transport"
echo "S3_BUILD_ROOT=$build_root"
echo "S3_CONFIG_ROOT_DER=${config_root/NONE/not-used}"
echo "S3_PAIRED_C3_ASSET=$node_asset"
echo "S3_PAIRED_C3_SHA256=$node_asset_sha"
echo "S3_PROJECT_VERSION=$project_version"
echo "S3_SDKCONFIG=$SDKCONFIG"
echo "S3_PARTITION_PROFILE=partitions.s3-outbox-candidate.csv"

source "$IDF_PATH/export.sh" >/dev/null
idf.py -C "$script_dir" -B "$build_dir" \
    "${cmake_args[@]}" reconfigure build size 2>&1 | tee "$build_root/idf-build.log"

sdkconfig="$SDKCONFIG"
cmake_cache="$build_dir/CMakeCache.txt"
partition_binary="$build_dir/partition_table/partition-table.bin"
partition_csv="$script_dir/partitions.s3-outbox-candidate.csv"
app_binary="$build_dir/gs_r1_s3_hub.bin"
python3 - "$profile" "$sdkconfig" "$cmake_cache" "$partition_binary" \
    "$partition_csv" "$app_binary" "$build_dir" "$config_root" \
    "$staged_node_asset" "$node_asset_sha" "$control_transport" <<'PY'
import hashlib
import pathlib
import re
import sys

profile, sdkconfig_path, cache_path, table_binary, table_csv, app_path, build_dir, root_path, node_path, expected_node_sha, control_transport = sys.argv[1:]
sdkconfig_path = pathlib.Path(sdkconfig_path)
cache_path = pathlib.Path(cache_path)
table_binary = pathlib.Path(table_binary)
table_csv = pathlib.Path(table_csv)
app_path = pathlib.Path(app_path)
build_dir = pathlib.Path(build_dir)
node_path = pathlib.Path(node_path)

def require(condition, message):
    if not condition:
        raise SystemExit(f"build-outbox verification failed: {message}")

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def read_config(path):
    result = {}
    for line in path.read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            result[line[2:].split(" is not set", 1)[0]] = "n"
    return result

def read_cache(path):
    result = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("//") or line.startswith("#") or "=" not in line:
            continue
        left, value = line.split("=", 1)
        key = left.split(":", 1)[0]
        result[key] = value
    return result

try:
    import gen_esp32part
except ImportError as error:
    idf_path = pathlib.Path("/home/udaybhan/.espressif/v6.0.3/esp-idf")
    sys.path.insert(0, str(idf_path / "components/partition_table"))
    import gen_esp32part

require(sdkconfig_path.is_file() and cache_path.is_file(), "missing generated SDK/CMake configuration")
require(table_binary.is_file() and table_csv.is_file(), "missing generated/source partition table")
require(app_path.is_file() and app_path.stat().st_size > 0, "missing S3 application image")
config = read_config(sdkconfig_path)
cache = read_cache(cache_path)
require(cache.get("IDF_TARGET") == "esp32s3", "CMake target is not ESP32-S3")
require(config.get("CONFIG_IDF_TARGET") == '"esp32s3"', "generated sdkconfig target is not ESP32-S3")
require(config.get("CONFIG_ESPTOOLPY_FLASHSIZE") == '"16MB"', "generated flash capacity differs from the registered S3 profile")
require(config.get("CONFIG_SPIRAM_MODE_OCT") == "y" and config.get("CONFIG_SPIRAM_SPEED") == "40", "generated PSRAM profile differs from the registered S3 profile")
require(config.get("CONFIG_PARTITION_TABLE_CUSTOM") == "y", "custom physical partition table is not selected")
require(config.get("CONFIG_PARTITION_TABLE_CUSTOM_FILENAME") == '"partitions.s3-outbox-candidate.csv"', "generated sdkconfig selected an unexpected partition CSV")

expected = {
    "nvs": (1, 2, 0x9000, 0x6000),
    "otadata": (1, 0, 0xF000, 0x2000),
    "phy_init": (1, 1, 0x11000, 0x1000),
    "ota_0": (0, 16, 0x20000, 0x400000),
    "ota_1": (0, 17, 0x420000, 0x400000),
    "gs_outbox": (1, 0x83, 0x820000, 0x400000),
    "gs_state": (1, 2, 0xC20000, 0x40000),
}
def partition_map(table):
    return {entry.name: (entry.type, entry.subtype, entry.offset, entry.size) for entry in table}

generated = gen_esp32part.PartitionTable.from_binary(table_binary.read_bytes())
source = gen_esp32part.PartitionTable.from_csv(table_csv.read_text())
require(partition_map(generated) == expected, "generated partition binary does not match the exact outbox/OTA/state layout")
require(partition_map(source) == expected, "canonical outbox partition CSV does not match its expected offsets/sizes")
require("gs_journal" not in partition_map(generated), "incompatible gs_journal partition is present")

expected_cmake = {
    "GS40_TEST_ONLY_CLOUDSYNC": "ON" if profile == "engineering" else "OFF",
    "GS_HIL_BUILD": "OFF",
    "GS_HIL_CONTROL": "OFF",
    "GS_HIL_COMMISSIONING": "OFF",
    "GS_HIL_C8_ACK_DROP": "OFF",
    "GS_HIL_C8_ACK_HOLD": "OFF",
    "GS_HIL_SIGNED_FOTA": "OFF",
    "GS_S3_DIAGNOSTIC_ONLY": "OFF",
    "GS68_CLOUDSYNC_DIAGNOSTIC_ONLY": "OFF",
}
for key, wanted in expected_cmake.items():
    require(cache.get(key) == wanted, f"CMake option {key} expected {wanted}, got {cache.get(key)}")
profile_defaults = cache.get("SDKCONFIG_DEFAULTS", "").split(";")
shared_defaults = [str(table_csv.parent / "sdkconfig.defaults"),
                   str(table_csv.parent / "sdkconfig.defaults.outbox")]
require(profile_defaults[:2] == shared_defaults, "generated SDK defaults do not begin with the shared outbox profile")
if profile == "engineering":
    expected_defaults = shared_defaults + [str(table_csv.parent / "sdkconfig.gs40_test_only.defaults")]
    if control_transport == "uart0":
        expected_defaults.append(str(table_csv.parent / "sdkconfig.gs40_test_only_uart.defaults"))
    require(profile_defaults == expected_defaults, "Engineering defaults do not match the registered control transport")
    require(cache.get("GS40_TEST_ONLY_CONFIG_ROOT_DER") == root_path, "GS40 root DER CMake input differs from fixture")
    require(config.get("CONFIG_ESP_TLS_USE_DS_PERIPHERAL") == "n", "Engineering TEST_ONLY software-key setting is absent")
    if control_transport == "uart0":
        require(config.get("CONFIG_ESP_CONSOLE_UART_DEFAULT") == "y" and config.get("CONFIG_ESP_CONSOLE_UART_NUM") == "0", "registered UART0 control profile is absent")
        require(config.get("CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG") == "n", "UART control selected a conflicting primary USB console")
    else:
        require(control_transport == "usb_serial_jtag", "unsupported Engineering control transport")
        require(config.get("CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG") == "y" and config.get("CONFIG_ESP_CONSOLE_UART_NUM") == "-1", "registered native USB control profile is absent")
    require(config.get("CONFIG_ESP_MAIN_TASK_STACK_SIZE") == "8192", "Engineering GS40 task-stack setting is absent")
    embedded_root = build_dir / "esp-idf/main/gs40_test_config_root.der"
    require(embedded_root.is_file() and sha(embedded_root) == sha(pathlib.Path(root_path)), "embedded GS40 config-root DER differs from the canonical fixture input")
else:
    require(profile_defaults == shared_defaults, "Release profile retained an Engineering sdkconfig defaults layer")
    require(not cache.get("GS40_TEST_ONLY_CONFIG_ROOT_DER"), "Release build retained a GS40 config-root input")

require(node_path.is_file() and sha(node_path) == expected_node_sha, "staged paired C3 asset changed")
ota_capacity = min(expected[name][3] for name in ("ota_0", "ota_1"))
require(app_path.stat().st_size <= ota_capacity, "S3 app image exceeds the OTA slot")
print("BUILD_PROFILE=" + profile)
print("IDF_TARGET=esp32s3")
print("PARTITION_TABLE=PASS entries=7 ota_0=0x20000/0x400000 ota_1=0x420000/0x400000 gs_outbox=0x820000/0x400000 gs_state=0xC20000/0x40000")
print(f"APP_IMAGE_BYTES={app_path.stat().st_size} OTA_SLOT_BYTES={ota_capacity} APP_SHA256={sha(app_path)}")
print(f"C3_ASSET_SHA256={sha(node_path)}")
PY

s3_image_info="$(esptool --chip esp32s3 image-info "$app_binary" 2>&1)"
if ! grep -Fq "Chip ID: 9 (ESP32-S3)" <<< "$s3_image_info"; then
    echo "Generated application image is not a compatible ESP32-S3 image." >&2
    exit 2
fi
c3_image_info="$(esptool --chip esp32c3 image-info "$staged_node_asset" 2>&1)"
if ! grep -Fq "Chip ID: 5 (ESP32-C3)" <<< "$c3_image_info"; then
    echo "Embedded application asset is not a compatible ESP32-C3 image." >&2
    exit 2
fi
echo "S3_IMAGE_TARGET=ESP32-S3"
echo "C3_ASSET_TARGET=ESP32-C3"
echo "S3_IMAGE_SHA256=$(sha256sum "$app_binary" | cut -d ' ' -f 1)"
echo "S3_IMAGE_BYTES=$(stat -c '%s' "$app_binary")"
echo "DEPLOYMENT_STATUS=BUILD_VERIFIED_ONLY_NO_HARDWARE_ACCESS"
