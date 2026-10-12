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
                                 embedded_node_asset: Path) -> dict:
    """Fail closed unless the standalone app matches the commissioned S3 profile."""
    cfg = parse_config(sdkconfig)
    cache = parse_config(cmake_cache)
    partitions = parse_partitions(partition_csv)
    required_cache = {
        "GS_HIL_BUILD": "OFF", "GS_HIL_CONTROL": "OFF",
        "GS_HIL_COMMISSIONING": "ON", "GS_S3_DIAGNOSTIC_ONLY": "OFF",
    }
    if any(cache.get(key) != value for key, value in required_cache.items()):
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
    # The complete S3 product image embeds its paired C3 firmware. A C3-only
    # command string must not be mistaken for an S3 UART command surface.
    # Verify that the paired C3 image has the physical-wake guard compiled in,
    # and that its synthetic-motion success path is absent.
    if (b"W (%lu) %s: HIL_ERROR command=INJECT_MOTION disabled_for_physical_wake" not in node_image
            or b"I (%lu) %s: HIL_OK command=INJECT_MOTION" in node_image):
        raise ValueError("embedded C3 asset does not enforce the physical-wake motion guard")
    s3_runtime_image = image[:embedded_at] + image[embedded_at + len(node_image):]
    missing_rpf = [marker.decode() for marker in RPF_MARKERS if marker not in image]
    missing_commissioning = [marker.decode() for marker in COMMISSIONING_MARKERS
                             if marker not in image]
    forbidden = [marker.decode() for marker in FORBIDDEN_HIL_MARKERS
                 if marker in s3_runtime_image]
    if missing_rpf or b"S3 replay fence failed stage=%s" not in image:
        raise ValueError(f"RPF diagnostics missing from S3 app: {missing_rpf}")
    if missing_commissioning:
        raise ValueError(f"fixture commissioning adapter missing: {missing_commissioning}")
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
        "commissioning_markers_present": [marker.decode() for marker in COMMISSIONING_MARKERS],
        "broad_hil_markers_absent": [marker.decode() for marker in FORBIDDEN_HIL_MARKERS],
        "embedded_node_asset_bytes": len(node_image),
        "embedded_node_asset_sha256": hashlib.sha256(node_image).hexdigest(),
        "embedded_node_asset_offset": embedded_at,
        "embedded_node_asset_physical_wake_guard_verified": True,
        "s3_runtime_image_broad_hil_markers_absent": True,
    }


def build(export: Path, project: Path, build_dir: Path, sdkconfig: Path,
          target: str, name: str, version: str, options: list[str]) -> Path:
    args = ["idf.py", "-C", str(project), "-B", str(build_dir),
            "-D", "SDKCONFIG=" + str(sdkconfig), "-D", "IDF_TARGET=" + target,
            "-D", "PROJECT_VER=" + version, "-D", "GS_HIL_BUILD=OFF"]
    args.extend(options)
    args.extend(["build", "size"])
    BUILD_COMMANDS[name] = args
    shell = "source " + shlex.quote(str(export)) + " >/dev/null 2>&1 && idf.py --version && " + shlex.join(args)
    log = build_dir.parent / (name + ".log")
    build_dir.mkdir(parents=True, exist_ok=True)
    with log.open("w") as output:
        result = subprocess.run(["bash", "-c", shell], cwd=ROOT, stdout=output,
                                 stderr=subprocess.STDOUT, timeout=1800)
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
    parser.add_argument("--s3-rpf-diagnostic", action="store_true",
                        help="build the S3 RPF01-RPF08 diagnostic in the commissioned fixture profile")
    args = parser.parse_args()
    export = Path(os.environ.get("GS_IDF_EXPORT", str(Path.home() / ".espressif/v6.0.3/esp-idf/export.sh")))
    if not export.is_file():
        raise RuntimeError("ESP-IDF 6.0.3 activation missing: " + str(export))
    out = ROOT / "build/gs114_fixture_pair"
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="build-", dir=out))
    fingerprint = source_fingerprint(extra=["scripts/build_gs114_fixture_pair.py"])
    head = subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, text=True).strip()
    suffix = "gs114-rpfdiag" if args.s3_rpf_diagnostic else "gs114"
    version = f"{head}-{suffix}-{fingerprint[:8]}"
    c3_project = ROOT / "firmware/node/target/esp32c3/idf"
    s3_project = ROOT / "firmware/hub/target/esp32s3/idf"
    c3_defaults = ";".join((str(c3_project / "sdkconfig.defaults"),
                            str(c3_project / "sdkconfig.hil.defaults")))
    c3 = build(export, c3_project, work / "c3", work / "c3-sdkconfig", "esp32c3", "c3", version,
               ["-D", "SDKCONFIG_DEFAULTS=" + c3_defaults,
                "-D", "GS_HIL_CONTROL=ON", "-D", "GS_BAT_C8_PHYSICAL_WAKE=ON"])
    asset = work / "assets/node_firmware.bin"
    asset.parent.mkdir()
    asset.write_bytes(c3.read_bytes())
    if asset.read_bytes() != c3.read_bytes():
        raise RuntimeError("embedded C3 asset differs from the paired C3 application")
    s3 = build(export, s3_project, work / "s3", work / "s3-sdkconfig", "esp32s3", "s3", version,
               ["-D", "GS_HIL_BUILD=OFF", "-D", "GS_HIL_CONTROL=OFF",
                "-D", "GS_HIL_COMMISSIONING=ON", "-D", "GS_S3_DIAGNOSTIC_ONLY=OFF",
                "-D", "SDKCONFIG_DEFAULTS=" + str(s3_project / "sdkconfig.defaults") + ";" + str(s3_project / "sdkconfig.defaults.outbox"),
                "-D", "GS_NODE_FIRMWARE_ASSET=" + str(asset)])
    if args.s3_rpf_diagnostic:
        partition_csv = s3_project / "partitions.s3-outbox-candidate.csv"
        if not partition_csv.is_file():
            raise RuntimeError("GS-114 outbox/state candidate partition table is missing")
        s3_profile = validate_s3_fixture_artifact(
            work / "s3-sdkconfig", work / "s3" / "CMakeCache.txt", partition_csv, s3, asset)
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
        "profile": ("GS-114 S3 fixture commissioning + RPF01-RPF08 diagnostic"
                    if args.s3_rpf_diagnostic else
                    "GS-114 disposable fixture; C3 HIL_CONTROL/physical wake; S3 commissioning-only"),
        "build_flags": {
            "c3": ["GS_HIL_BUILD=OFF", "GS_HIL_CONTROL=ON", "GS_BAT_C8_PHYSICAL_WAKE=ON"],
            "s3": ["GS_HIL_BUILD=OFF", "GS_HIL_CONTROL=OFF", "GS_HIL_COMMISSIONING=ON",
                   "GS_S3_DIAGNOSTIC_ONLY=OFF"],
        },
        "build_commands": BUILD_COMMANDS,
        "build_logs": {
            "c3": str(work / "c3.log"),
            "s3": str(work / "s3.log"),
        },
        "configuration": ({
            "s3_sdkconfig": str(work / "s3-sdkconfig"),
            "sdkconfig_defaults": [str(s3_project / "sdkconfig.defaults"),
                                   str(s3_project / "sdkconfig.defaults.outbox")],
            "partition_csv": str(s3_project / "partitions.s3-outbox-candidate.csv"),
            "partition_csv_sha256": hashlib.sha256(
                (s3_project / "partitions.s3-outbox-candidate.csv").read_bytes()).hexdigest(),
            "s3_profile_validation": s3_profile,
        } if args.s3_rpf_diagnostic else {}),
        "full_device_package": {
            "status": "NOT_AUTHORIZED_FOR_DEPLOYMENT",
            "flash_command_invoked": False,
            "contains_bootloader_partition_table_otadata_and_app": True,
        },
        "artifacts": {}, "hardware_actions": "NONE", "physical_status": "NOT_RUN",
        "deployment": {"authorized": False, "status": "NOT_INSTALLED",
                       "full_device_bundle": "NOT_AUTHORIZED_FOR_DEPLOYMENT"},
    }
    for role, image in (("c3", c3), ("s3", s3)):
        data = image.read_bytes()
        result["artifacts"][role] = {"path": str(image), "bytes": len(data),
                                      "sha256": hashlib.sha256(data).hexdigest()}
    for role, image in (("c3", c3), ("s3", s3)):
        result["artifacts"][role]["image_info"] = idf_image_info(export, image)
    if args.s3_rpf_diagnostic:
        result["artifacts"]["s3"]["ota_slot_capacity_bytes"] = s3_profile["ota_slot_capacity_bytes"]
        result["artifacts"]["s3"]["ota_slot_free_bytes"] = s3_profile["app_free_bytes"]
        result["artifacts"]["s3"]["status"] = "STANDALONE_APP_BUILT_NOT_INSTALLED"
    report = work / "fixture_pair_report.json"
    report.write_text(json.dumps(result, indent=2) + "\n")
    print("GS114 FIXTURE PAIR BUILDS PASS")
    print("FIXTURE BUILD REPORT", report)
    print("C3", result["artifacts"]["c3"])
    print("S3", result["artifacts"]["s3"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("GS114 FIXTURE PAIR BUILDS FAIL:", exc, file=sys.stderr)
        raise SystemExit(1)
