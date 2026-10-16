#!/usr/bin/env python3
"""Build a disposable C3/S3 GS-114 pair; no serial or hardware access."""
from pathlib import Path
import argparse, csv, hashlib, json, os, shlex, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation.component_gate import source_fingerprint

FIXTURE_PARTITIONS = {
    "ota_0": ("app", "ota_0", 0x20000, 0x400000),
    "ota_1": ("app", "ota_1", 0x420000, 0x400000),
    "gs_outbox": ("data", "littlefs", 0x820000, 0x400000),
    "gs_state": ("data", "nvs", 0xC20000, 0x40000),
}
RPF_MARKERS = tuple(f"RPF0{i}".encode() for i in range(9))
COMMISSIONING_MARKERS = (b"COMMISSION_EXPECTED_NODE", b"FIXTURE_STATUS", b"HIL_FIXTURE_READY")
FORBIDDEN_HIL_MARKERS = (b"INJECT_MOTION", b"START_C3_FOTA", b"HIL_GPIO")
BUILD_COMMANDS = {}


def build_environment(options: list[str], base_environment=None) -> dict[str, str]:
    env = dict(os.environ if base_environment is None else base_environment)
    for option in options:
        if option.startswith("GS_NODE_FIRMWARE_ASSET="):
            env["GS_NODE_FIRMWARE_ASSET"] = option.split("=", 1)[1]
    return env


def stage_node_firmware_asset(work: Path, source: Path,
                              expected_sha256: str | None = None,
                              require_ack_trace: bool = False) -> tuple[Path, dict]:
    """Stage a byte-verified C3 app at the filename required by S3 component discovery."""
    source = source.resolve()
    if not source.is_file():
        raise ValueError(f"C3 firmware asset does not exist: {source}")
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None:
        expected = expected_sha256.lower()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            raise ValueError("expected C3 firmware SHA-256 must be 64 hexadecimal characters")
        if digest != expected:
            raise ValueError(f"C3 firmware asset SHA-256 mismatch: expected {expected}, got {digest}")
    asset = work / "assets" / "node_firmware.bin"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(data)
    staged_digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    if staged_digest != digest:
        raise RuntimeError("staged C3 firmware asset differs from its verified source")
    ack_trace_marker = b"GS114_ACK_WAIT_TRACE_SCHEMA=1" in data
    if require_ack_trace and not ack_trace_marker:
        raise ValueError("P9 image requires a C3 app with the test-only ACK-wait trace profile")
    return asset, {
        "source_path": str(source), "staged_path": str(asset),
        "bytes": len(data), "sha256": digest,
        "expected_sha256": expected_sha256,
        "reused_existing_image": expected_sha256 is not None,
        "ack_wait_trace_profile_verified": ack_trace_marker,
    }


def c3_p9_build_profile() -> tuple[list[str], list[str]]:
    """Return the minimal real-wake P9 C3 config without the UART HIL plane."""
    defaults = ["sdkconfig.defaults"]
    options = ["-D", "GS_HIL_CONTROL=OFF", "-D", "GS_BAT_C8_PHYSICAL_WAKE=ON",
               "-D", "GS_BAT_C8_ACK_TRACE=ON",
               "-D", "GS_BAT_C8_FIXTURE_SECURITY=ON"]
    return defaults, options


def validate_c3_p9_ack_trace_profile(sdkconfig: Path, cmake_cache: Path,
                                     app: Path) -> dict:
    """Fail closed unless P9 embeds a real-wake trace app without UART controls."""
    cfg = parse_config(sdkconfig)
    cache = parse_config(cmake_cache)
    required_cache = {
        "GS_HIL_BUILD": "OFF",
        "GS_HIL_CONTROL": "OFF",
        "GS_BAT_C8_PHYSICAL_WAKE": "ON",
        "GS_BAT_C8_ACK_TRACE": "ON",
        "GS_BAT_C8_FIXTURE_SECURITY": "ON",
    }
    if any(cache.get(key) != value for key, value in required_cache.items()):
        raise ValueError("C3 P9 profile must use physical wake and ACK trace with HIL controls off")
    if cfg.get("CONFIG_ESPTOOLPY_FLASHSIZE") != "4MB" or \
            cfg.get("CONFIG_PARTITION_TABLE_CUSTOM_FILENAME") != "partitions.csv":
        raise ValueError("C3 P9 profile must retain the qualified 4 MiB partition configuration")
    if cfg.get("CONFIG_ESP_CONSOLE_UART_DEFAULT") != "y" or \
            cfg.get("CONFIG_ESP_CONSOLE_UART_NUM") != "0" or \
            cfg.get("CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG") == "y":
        raise ValueError("C3 P9 profile must select UART0 as primary console, not USB HIL console defaults")
    data = app.read_bytes()
    if b"GS114_ACK_WAIT_TRACE_SCHEMA=1" not in data:
        raise ValueError("C3 P9 profile is missing the ACK-wait trace")
    if b"STA MAC does not match qualified C3" not in data:
        raise ValueError("C3 P9 profile is missing its exact-board identity guard")
    if b"GS114_C8_FIXTURE_SECURITY=TEST_ONLY; UART_HIL_CONTROL=OFF" not in data or \
            b"gs_dev_ident" not in data:
        raise ValueError("C3 P9 profile is missing its explicitly test-only R&D identity path")
    forbidden = (b"HIL_READY", b"INJECT_MOTION", b"GET_HEALTH", b"GET_STATE",
                 b"GET_TEST_QR", b"SOFTWARE_RESTART")
    present = [marker.decode() for marker in forbidden if marker in data]
    if present:
        raise ValueError(f"C3 P9 profile contains unrelated UART HIL controls: {present}")
    return {
        "build_options": required_cache,
        "flash_bytes": 4 * 1024 * 1024,
        "partition_table": "partitions.csv",
        "primary_console": "UART0",
        "usb_hil_console": False,
        "qualified_node_mac_guard": True,
        "test_identity_path": "gs_dev_ident; read-only existing NVS identity; HIL command plane disabled",
        "ack_wait_trace": True,
        "uart_hil_command_markers_absent": [marker.decode() for marker in forbidden],
    }


def parse_config(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("# CONFIG_") and line.endswith(" is not set"):
            result[line[2:].split(" is not set", 1)[0]] = "n"
            continue
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.split(":", 1)[0]
        result[key] = value.strip('"')
    return result


def parse_partitions(path: Path) -> dict[str, tuple[str, str, int, int]]:
    with path.open(newline="") as source:
        return parse_partitions_from_text(source.read())


def parse_partition_number(value: str) -> int:
    value = value.strip().upper()
    for suffix, multiplier in (("K", 1024), ("M", 1024 ** 2), ("G", 1024 ** 3)):
        if value.endswith(suffix):
            return int(value[:-1], 0) * multiplier
    return int(value, 0)


def parse_partitions_from_text(text: str) -> dict[str, tuple[str, str, int, int]]:
    result = {}
    for row in csv.reader(text.splitlines(), skipinitialspace=True):
        if not row or row[0].lstrip().startswith("#"):
            continue
        row = [cell.strip() for cell in row]
        if len(row) < 5:
            raise ValueError(f"invalid partition row: {row!r}")
        result[row[0]] = (row[1], row[2], parse_partition_number(row[3]),
                           parse_partition_number(row[4]))
    return result


def validate_s3_fixture_artifact(sdkconfig: Path, cmake_cache: Path,
                                 partition_csv: Path, app: Path,
                                 embedded_node_asset: Path,
                                 c8_ack_drop: bool = False,
                                 c8_ack_hold: bool = False,
                                 fixture_commissioning: bool = True) -> dict:
    """Fail closed unless the standalone app matches the commissioned S3 profile."""
    cfg = parse_config(sdkconfig)
    cache = parse_config(cmake_cache)
    partitions = parse_partitions(partition_csv)
    required_cache = {
        "GS_HIL_BUILD": "OFF", "GS_HIL_CONTROL": "OFF",
        "GS_HIL_COMMISSIONING": "ON" if fixture_commissioning else "OFF",
        "GS_S3_DIAGNOSTIC_ONLY": "OFF",
        "GS_HIL_C8_ACK_DROP": "ON" if c8_ack_drop else "OFF",
        "GS_HIL_C8_ACK_HOLD": "ON" if c8_ack_hold else "OFF",
        "GS_HIL_SIGNED_FOTA": "OFF",
    }
    # Older isolated fixture builds predate these two options; CMake's
    # effective default was OFF. The P9 profile still requires an explicit ON.
    if any(cache.get(key, "OFF" if key in {"GS_HIL_C8_ACK_HOLD", "GS_HIL_SIGNED_FOTA"} else None) != value
           for key, value in required_cache.items()):
        raise ValueError("S3 fixture CMake options do not match the approved isolated profile")
    required_config = {
        "CONFIG_ESPTOOLPY_FLASHSIZE": "16MB",
        "CONFIG_PARTITION_TABLE_CUSTOM_FILENAME": partition_csv.name,
        "CONFIG_SPIRAM_MODE_OCT": "y", "CONFIG_SPIRAM_SPEED": "40",
        "CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE": "y",
        "CONFIG_ESPTOOLPY_FLASHMODE": "dio", "CONFIG_ESPTOOLPY_FLASHFREQ": "40m",
        "CONFIG_SECURE_BOOT": "n", "CONFIG_FLASH_ENCRYPTION_ENABLED": "n",
        "CONFIG_APP_ANTI_ROLLBACK": "n",
    }
    if any(cfg.get(key) != value for key, value in required_config.items()):
        raise ValueError("S3 sdkconfig does not match the commissioned flash/PSRAM/OTA profile")
    if any(partitions.get(name) != value for name, value in FIXTURE_PARTITIONS.items()):
        raise ValueError("S3 partition table does not match gs_outbox/gs_state fixture layout")
    size = app.stat().st_size
    slot_sizes = [partitions[name][3] for name in ("ota_0", "ota_1")]
    capacity = min(slot_sizes)
    if size == 0 or size > capacity:
        raise ValueError(f"S3 app size {size} is outside OTA slot capacity {capacity}")
    image = app.read_bytes()
    node_image = embedded_node_asset.read_bytes()
    embedded_at = image.find(node_image)
    if not node_image or embedded_at < 0 or image.count(node_image) != 1:
        raise ValueError("S3 app does not contain exactly one byte-identical paired C3 asset")
    ack_trace_profile_verified = b"GS114_ACK_WAIT_TRACE_SCHEMA=1" in node_image
    if c8_ack_hold and not ack_trace_profile_verified:
        raise ValueError("P9 S3 fixture must embed a C3 app with ACK-wait trace enabled")
    c3_hil_markers = (b"HIL_READY", b"INJECT_MOTION", b"GET_HEALTH", b"GET_STATE",
                      b"GET_TEST_QR", b"SOFTWARE_RESTART")
    if c8_ack_hold:
        if any(marker in node_image for marker in c3_hil_markers):
            raise ValueError("embedded P9 C3 image must omit the unrelated UART HIL command plane")
        if b"STA MAC does not match qualified C3" not in node_image:
            raise ValueError("embedded P9 C3 image is missing its qualified-board identity guard")
        if b"GS114_C8_FIXTURE_SECURITY=TEST_ONLY; UART_HIL_CONTROL=OFF" not in node_image or \
                b"gs_dev_ident" not in node_image:
            raise ValueError("embedded P9 C3 image is missing its test-only R&D identity profile")
    elif (b"W (%lu) %s: HIL_ERROR command=INJECT_MOTION disabled_for_physical_wake" not in node_image
          or b"I (%lu) %s: HIL_OK command=INJECT_MOTION" in node_image):
        raise ValueError("embedded C3 asset does not enforce the physical-wake motion guard")
    s3_runtime_image = image[:embedded_at] + image[embedded_at + len(node_image):]
    missing_rpf = [marker.decode() for marker in RPF_MARKERS if marker not in image]
    missing_commissioning = ([marker.decode() for marker in COMMISSIONING_MARKERS
                              if marker not in image] if fixture_commissioning else [])
    unexpected_commissioning = (not fixture_commissioning and any(
        marker in image for marker in COMMISSIONING_MARKERS[:2]))
    forbidden = [marker.decode() for marker in FORBIDDEN_HIL_MARKERS
                 if marker in s3_runtime_image]
    if missing_rpf or b"S3 replay fence failed stage=%s" not in image:
        raise ValueError(f"RPF diagnostics missing from S3 app: {missing_rpf}")
    if missing_commissioning:
        raise ValueError(f"fixture commissioning adapter missing: {missing_commissioning}")
    if unexpected_commissioning:
        raise ValueError("P9 fixture unexpectedly contains node commissioning commands")
    ack_drop_marker = b"DROP_NEXT_DURABLE_ACK"
    if (ack_drop_marker in s3_runtime_image) != c8_ack_drop:
        raise ValueError("S3 C8 ACK-drop command does not match the selected fixture profile")
    if (b"ARM_C8_ACK_HOLD" in s3_runtime_image) != c8_ack_hold:
        raise ValueError("S3 C8 ACK-hold command does not match the selected fixture profile")
    if forbidden:
        raise ValueError(f"broad HIL control marker present in S3 app: {forbidden}")
    return {
        "build_options": required_cache,
        "sdkconfig": {key: cfg[key] for key in required_config},
        "partitions": {name: {"type": values[0], "subtype": values[1],
                              "offset": f"0x{values[2]:x}", "size": values[3]}
                       for name, values in partitions.items()},
        "ota_slot_capacity_bytes": capacity,
        "app_bytes": size,
        "app_free_bytes": capacity - size,
        "rpf_markers_present": [marker.decode() for marker in RPF_MARKERS],
        "commissioning_markers_present": [marker.decode() for marker in COMMISSIONING_MARKERS
                                           if marker in image],
        "c8_ack_drop_fixture_enabled": c8_ack_drop,
        "c8_ack_hold_fixture_enabled": c8_ack_hold,
        "broad_hil_markers_absent": [marker.decode() for marker in FORBIDDEN_HIL_MARKERS],
        "embedded_node_asset_bytes": len(node_image),
        "embedded_node_asset_sha256": hashlib.sha256(node_image).hexdigest(),
        "embedded_node_asset_offset": embedded_at,
        "embedded_node_asset_physical_wake_guard_verified":
            b"W (%lu) %s: HIL_ERROR command=INJECT_MOTION disabled_for_physical_wake" in node_image
            or ack_trace_profile_verified,
        "embedded_node_asset_ack_wait_trace_verified": ack_trace_profile_verified,
        "embedded_node_asset_hil_command_plane_absent": c8_ack_hold,
        "embedded_node_asset_qualified_mac_guard_verified":
            b"STA MAC does not match qualified C3" in node_image,
        "embedded_node_asset_fixture_security_verified":
            b"GS114_C8_FIXTURE_SECURITY=TEST_ONLY; UART_HIL_CONTROL=OFF" in node_image
            and b"gs_dev_ident" in node_image,
        "s3_runtime_image_broad_hil_markers_absent": True,
    }


def build(export: Path, project: Path, build_dir: Path, sdkconfig: Path,
          target: str, name: str, version: str, options: list[str]) -> Path:
    idf_script = export.parent / "tools/idf.py"
    args = ["idf.py", "-C", str(project), "-B", str(build_dir),
            "-D", "SDKCONFIG=" + str(sdkconfig), "-D", "IDF_TARGET=" + target,
            "-D", "PROJECT_VER=" + version, "-D", "GS_HIL_BUILD=OFF"]
    args.extend(options)
    args.extend(["build", "size"])
    BUILD_COMMANDS[name] = args
    idf_runner = '"$ESP_PYTHON" ' + shlex.quote(str(idf_script))
    shell = ("source " + shlex.quote(str(export)) + " >/dev/null 2>&1 && "
             + idf_runner + " --version && " + idf_runner + " " + shlex.join(args[1:]))
    # IDF may evaluate component requirements before the project's -D cache
    # value is visible. Make the paired C3 image available during discovery.
    build_env = build_environment(options)
    log = build_dir.parent / (name + ".log")
    build_dir.mkdir(parents=True, exist_ok=True)
    with log.open("w") as output:
        result = subprocess.run(["bash", "-c", shell], cwd=ROOT, stdout=output,
                                 stderr=subprocess.STDOUT, timeout=1800, env=build_env)
    if result.returncode != 0 or "ESP-IDF v6.0.3" not in log.read_text():
        raise RuntimeError(f"{name} build failed; see {log}")
    expected = "gs_hw_m1_node.bin" if name == "c3" else "gs_r1_s3_hub.bin"
    image = build_dir / expected
    if not image.is_file():
        raise RuntimeError(f"{name} image missing: {image}")
    return image


def idf_image_info(export: Path, image: Path) -> str:
    shell = "source " + shlex.quote(str(export)) + " >/dev/null 2>&1 && esptool image-info " + shlex.quote(str(image))
    return subprocess.run(["bash", "-c", shell], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--s3-rpf-diagnostic", action="store_true",
                       help="build the S3 RPF01-RPF08 diagnostic in the commissioned fixture profile")
    group.add_argument("--s3-c8-p8-ack-drop", action="store_true",
                       help="build the S3 commissioning profile with one-shot C8-P8 ACK suppression")
    group.add_argument("--s3-c8-p9-ack-hold", action="store_true",
                       help="build the S3 commissioning profile with bounded exact-key C8-P9 ACK hold")
    parser.add_argument("--s3-node-firmware-asset", type=Path,
                        help="reuse a verified existing C3 app as the S3 embedded node asset; requires a focused C8 fixture")
    parser.add_argument("--expected-node-sha256",
                        help="required SHA-256 when reusing --s3-node-firmware-asset")
    args = parser.parse_args()
    if args.s3_node_firmware_asset is not None and not (args.s3_c8_p8_ack_drop or args.s3_c8_p9_ack_hold):
        parser.error("--s3-node-firmware-asset is only supported with --s3-c8-p8-ack-drop or --s3-c8-p9-ack-hold")
    if args.s3_node_firmware_asset is not None and args.expected_node_sha256 is None:
        parser.error("--expected-node-sha256 is required with --s3-node-firmware-asset")
    if args.expected_node_sha256 is not None and args.s3_node_firmware_asset is None:
        parser.error("--expected-node-sha256 requires --s3-node-firmware-asset")
    export = Path(os.environ.get("GS_IDF_EXPORT", str(Path.home() / ".espressif/v6.0.3/esp-idf/export.sh")))
    if not export.is_file():
        raise RuntimeError("ESP-IDF 6.0.3 activation missing: " + str(export))
    out = ROOT / "build/gs114_fixture_pair"
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="build-", dir=out))
    fingerprint = source_fingerprint(extra=["scripts/build_gs114_fixture_pair.py"])
    head = subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, text=True).strip()
    suffix = ("gs114-rpfdiag" if args.s3_rpf_diagnostic else
              "gs114-c8p8" if args.s3_c8_p8_ack_drop else
              "gs114-c8p9" if args.s3_c8_p9_ack_hold else "gs114")
    version = f"{head}-{suffix}-{fingerprint[:8]}"
    c3_project = ROOT / "firmware/node/target/esp32c3/idf"
    s3_project = ROOT / "firmware/hub/target/esp32s3/idf"
    c3_p9_defaults, c3_p9_options = c3_p9_build_profile()
    c3_default_files = (c3_p9_defaults if args.s3_c8_p9_ack_hold else
                        ["sdkconfig.defaults", "sdkconfig.hil.defaults"])
    c3_defaults = ";".join(str(c3_project / item) for item in c3_default_files)
    c3_profile = None
    if args.s3_node_firmware_asset is not None:
        c3 = None
        asset, node_asset_report = stage_node_firmware_asset(
            work, args.s3_node_firmware_asset, args.expected_node_sha256,
            require_ack_trace=args.s3_c8_p9_ack_hold)
    else:
        c3_options = ["-D", "SDKCONFIG_DEFAULTS=" + c3_defaults]
        if args.s3_c8_p9_ack_hold:
            c3_options.extend(c3_p9_options)
        else:
            c3_options.extend(["-D", "GS_HIL_CONTROL=ON",
                               "-D", "GS_BAT_C8_PHYSICAL_WAKE=ON"])
        c3 = build(export, c3_project, work / "c3", work / "c3-sdkconfig", "esp32c3", "c3", version,
                   c3_options)
        c3_profile = (validate_c3_p9_ack_trace_profile(
            work / "c3-sdkconfig", work / "c3" / "CMakeCache.txt", c3)
            if args.s3_c8_p9_ack_hold else None)
        asset, node_asset_report = stage_node_firmware_asset(
            work, c3, require_ack_trace=args.s3_c8_p9_ack_hold)
    fixture_commissioning = not args.s3_c8_p9_ack_hold
    s3 = build(export, s3_project, work / "s3", work / "s3-sdkconfig", "esp32s3", "s3", version,
               ["-D", "GS_HIL_BUILD=OFF", "-D", "GS_HIL_CONTROL=OFF",
                "-D", "GS_HIL_COMMISSIONING=" + ("ON" if fixture_commissioning else "OFF"),
                "-D", "GS_S3_DIAGNOSTIC_ONLY=OFF",
                "-D", "GS_HIL_C8_ACK_DROP=" + ("ON" if args.s3_c8_p8_ack_drop else "OFF"),
                "-D", "GS_HIL_C8_ACK_HOLD=" + ("ON" if args.s3_c8_p9_ack_hold else "OFF"),
                "-D", "GS_HIL_SIGNED_FOTA=OFF",
                "-D", "SDKCONFIG_DEFAULTS=" + str(s3_project / "sdkconfig.defaults") + ";" + str(s3_project / "sdkconfig.defaults.outbox"),
                "-D", "GS_NODE_FIRMWARE_ASSET=" + str(asset)])
    if args.s3_rpf_diagnostic or args.s3_c8_p8_ack_drop or args.s3_c8_p9_ack_hold:
        partition_csv = s3_project / "partitions.s3-outbox-candidate.csv"
        if not partition_csv.is_file():
            raise RuntimeError("GS-114 outbox/state candidate partition table is missing")
        s3_profile = validate_s3_fixture_artifact(
            work / "s3-sdkconfig", work / "s3" / "CMakeCache.txt", partition_csv,
            s3, asset, c8_ack_drop=args.s3_c8_p8_ack_drop,
            c8_ack_hold=args.s3_c8_p9_ack_hold,
            fixture_commissioning=fixture_commissioning)
        compiled_table = work / "s3" / "partition_table" / "partition-table.bin"
        idf_path = os.environ.get("IDF_PATH", str(export.parent))
        converter = Path(idf_path or "") / "components/partition_table/gen_esp32part.py"
        if not compiled_table.is_file() or not converter.is_file():
            raise RuntimeError("compiled S3 partition table/provenance tool is missing")
        decoded = subprocess.run([sys.executable, str(converter), str(compiled_table)],
                                 check=True, capture_output=True, text=True).stdout
        compiled_partitions = parse_partitions_from_text(decoded)
        if any(compiled_partitions.get(name) != value
               for name, value in FIXTURE_PARTITIONS.items()):
            raise RuntimeError("compiled ESP-IDF partition table differs from fixture CSV")
        s3_profile["compiled_partition_table_sha256"] = hashlib.sha256(compiled_table.read_bytes()).hexdigest()
        s3_profile["compiled_partition_table_matches_csv"] = True
        s3_profile["compiled_partition_rows"] = {
            name: {"type": value[0], "subtype": value[1],
                   "offset": f"0x{value[2]:x}", "size": value[3]}
            for name, value in compiled_partitions.items()
        }
    else:
        s3_profile = None
    result = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_fingerprint": fingerprint, "idf": "6.0.3",
        "profile": ("GS-114 S3 commissioning + RPF01-RPF08 + isolated C8-P8 ACK-drop fixture"
                    if args.s3_c8_p8_ack_drop else
                    "GS-114 S3 bounded exact-key C8-P9 ACK-hold fixture"
                    if args.s3_c8_p9_ack_hold else
                    "GS-114 S3 fixture commissioning + RPF01-RPF08 diagnostic"
                    if args.s3_rpf_diagnostic else
                    "GS-114 disposable fixture; C3 HIL_CONTROL/physical wake; S3 commissioning-only"),
        "build_flags": {
            "c3": (["GS_HIL_BUILD=OFF",
                    "GS_HIL_CONTROL=" + ("OFF" if args.s3_c8_p9_ack_hold else "ON"),
                    "GS_BAT_C8_PHYSICAL_WAKE=ON"] +
                   (["GS_BAT_C8_ACK_TRACE=ON", "GS_BAT_C8_FIXTURE_SECURITY=ON"]
                    if args.s3_c8_p9_ack_hold else [])
                   if c3 is not None else ["NOT_BUILT; verified existing image reused as S3 input"]),
            "s3": ["GS_HIL_BUILD=OFF", "GS_HIL_CONTROL=OFF",
                   "GS_HIL_COMMISSIONING=" + ("ON" if fixture_commissioning else "OFF"),
                   "GS_S3_DIAGNOSTIC_ONLY=OFF",
                   "GS_HIL_C8_ACK_DROP=" + ("ON" if args.s3_c8_p8_ack_drop else "OFF"),
                   "GS_HIL_C8_ACK_HOLD=" + ("ON" if args.s3_c8_p9_ack_hold else "OFF"),
                   "GS_HIL_SIGNED_FOTA=OFF"],
        },
        "build_commands": BUILD_COMMANDS,
        "build_logs": {
            "c3": str(work / "c3.log") if c3 is not None else None,
            "s3": str(work / "s3.log"),
        },
        "node_firmware_asset": node_asset_report,
        "configuration": ({
            "s3_sdkconfig": str(work / "s3-sdkconfig"),
            "sdkconfig_defaults": [str(s3_project / "sdkconfig.defaults"),
                                   str(s3_project / "sdkconfig.defaults.outbox")],
            "partition_csv": str(s3_project / "partitions.s3-outbox-candidate.csv"),
            "partition_csv_sha256": hashlib.sha256(
                (s3_project / "partitions.s3-outbox-candidate.csv").read_bytes()).hexdigest(),
            "s3_profile_validation": s3_profile,
            **({"c3_profile_validation": c3_profile} if c3_profile is not None else {}),
        } if args.s3_rpf_diagnostic or args.s3_c8_p8_ack_drop or args.s3_c8_p9_ack_hold else {}),
        "full_device_package": {
            "status": "NOT_AUTHORIZED_FOR_DEPLOYMENT",
            "flash_command_invoked": False,
            "contains_bootloader_partition_table_otadata_and_app": True,
        },
        "artifacts": {}, "hardware_actions": "NONE", "physical_status": "NOT_RUN",
        "deployment": {"authorized": False, "status": "NOT_INSTALLED",
                       "full_device_bundle": "NOT_AUTHORIZED_FOR_DEPLOYMENT"},
    }
    built_images = ([ ("c3", c3) ] if c3 is not None else []) + [("s3", s3)]
    for role, image in built_images:
        data = image.read_bytes()
        result["artifacts"][role] = {"path": str(image), "bytes": len(data),
                                      "sha256": hashlib.sha256(data).hexdigest()}
    for role, image in built_images:
        result["artifacts"][role]["image_info"] = idf_image_info(export, image)
    if c3 is None:
        result["node_firmware_asset"]["image_info"] = idf_image_info(export, asset)
    if args.s3_rpf_diagnostic or args.s3_c8_p8_ack_drop or args.s3_c8_p9_ack_hold:
        result["artifacts"]["s3"]["ota_slot_capacity_bytes"] = s3_profile["ota_slot_capacity_bytes"]
        result["artifacts"]["s3"]["ota_slot_free_bytes"] = s3_profile["app_free_bytes"]
        result["artifacts"]["s3"]["status"] = "STANDALONE_APP_BUILT_NOT_INSTALLED"
    report = work / "fixture_pair_report.json"
    report.write_text(json.dumps(result, indent=2) + "\n")
    print("GS114 FIXTURE PAIR BUILDS PASS")
    print("FIXTURE BUILD REPORT", report)
    print("C3", result["artifacts"].get("c3", result["node_firmware_asset"]))
    print("S3", result["artifacts"]["s3"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("GS114 FIXTURE PAIR BUILDS FAIL:", exc, file=sys.stderr)
        raise SystemExit(1)
