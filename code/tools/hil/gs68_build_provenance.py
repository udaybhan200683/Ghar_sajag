"""Shared deterministic input manifest for GS-68 TEST_ONLY S3 builds."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA = "gs68.build-inputs.v1"
EXPECTED_BUILD_CONFIGURATION = {
    "idf_target": "esp32s3", "diagnostic_profile": "GS68_CLOUDSYNC_DS_MTLS_HIL",
    "gs68_cloudsync_diagnostic_only": True, "gs_hil_build": False,
    "gs_hil_control": False, "gs_hil_commissioning": False,
    "gs_hil_c8_ack_drop": False, "tls_version": "TLS1.2",
    "console_primary": "USB_SERIAL_JTAG", "console_uart0_primary": False,
    "console_usb_secondary": False, "stdin_read_mode": "USB_DRIVER_BLOCKING",
    "hardware_signer": "ESP32_DS_PERIPHERAL_SELECTED_NOT_PROVISIONED",
}
PROFILE = Path("code/firmware/hub/target/esp32s3/idf/sdkconfig.gs68_cloudsync_hil.defaults")
PARTITIONS = Path("code/firmware/hub/target/esp32s3/idf/partitions.development.csv")
DEPENDENCIES = Path("code/firmware/hub/target/esp32s3/idf/dependencies.lock")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: Path) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = file_path.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(file_path)))
    return digest.hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def build_input_manifest(repo: Path, *, source_code_tree_oid: str, idf_version: str,
                         effective_sdkconfig_sha256: str,
                         build_configuration: dict,
                         effective_sdkconfig_path: Path | None = None,
                         partition_table_binary_path: Path | None = None) -> dict:
    repo = Path(repo).resolve()
    files = {}
    for label, relative in (("profile", PROFILE), ("partition_table_csv", PARTITIONS),
                            ("dependencies_lock", DEPENDENCIES)):
        path = repo / relative
        if not path.is_file():
            raise FileNotFoundError(f"required GS-68 build input is missing: {relative}")
        files[label] = {"path": relative.as_posix(), "sha256": sha256_file(path)}
    managed = repo / "code/firmware/hub/target/esp32s3/idf/managed_components"
    if not managed.is_dir():
        raise FileNotFoundError("ESP-IDF managed component inputs are unavailable")
    files["managed_components"] = {"path": str(managed), "sha256": sha256_tree(managed)}
    if effective_sdkconfig_path is not None:
        sdkconfig_path = Path(effective_sdkconfig_path).resolve()
        files["effective_sdkconfig"] = {"path": str(sdkconfig_path),
                                        "sha256": sha256_file(sdkconfig_path)}
        if files["effective_sdkconfig"]["sha256"] != effective_sdkconfig_sha256:
            raise ValueError("effective sdkconfig hash differs from build report")
    if partition_table_binary_path is not None:
        partition_path = Path(partition_table_binary_path).resolve()
        files["partition_table_binary"] = {"path": str(partition_path),
                                            "sha256": sha256_file(partition_path)}
    return {
        "schema": SCHEMA,
        "source_code_tree_oid": source_code_tree_oid,
        "idf_version": idf_version,
        "target": "esp32s3",
        "effective_sdkconfig_sha256": effective_sdkconfig_sha256,
        "build_configuration": build_configuration,
        "files": files,
    }


def fingerprint(manifest: dict) -> str:
    return hashlib.sha256(canonical_json(manifest)).hexdigest()


def validate_manifest(repo: Path, manifest: object, expected_fingerprint: object) -> list[str]:
    """Recompute all declared source/build inputs; malformed manifests fail closed."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        return ["build input manifest is missing or has an unsupported schema"]
    errors = []
    if not isinstance(expected_fingerprint, str) or fingerprint(manifest) != expected_fingerprint:
        errors.append("build input manifest fingerprint mismatch")
    if manifest.get("build_configuration") != EXPECTED_BUILD_CONFIGURATION:
        errors.append("effective GS-68 TEST_ONLY build configuration is not the approved profile")
    try:
        sdkconfig_entry = manifest.get("files", {}).get("effective_sdkconfig", {})
        partition_entry = manifest.get("files", {}).get("partition_table_binary", {})
        actual = build_input_manifest(
            repo,
            source_code_tree_oid=manifest.get("source_code_tree_oid"),
            idf_version=manifest.get("idf_version"),
            effective_sdkconfig_sha256=manifest.get("effective_sdkconfig_sha256"),
            build_configuration=manifest.get("build_configuration"),
            effective_sdkconfig_path=sdkconfig_entry.get("path") if isinstance(sdkconfig_entry, dict) else None,
            partition_table_binary_path=partition_entry.get("path") if isinstance(partition_entry, dict) else None,
        )
    except (OSError, TypeError, ValueError):
        return errors + ["required build input is unavailable"]
    if canonical_json(actual) != canonical_json(manifest):
        errors.append("build inputs, profile, partition table, dependencies, or configuration changed")
    return errors
