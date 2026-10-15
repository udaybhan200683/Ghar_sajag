#!/usr/bin/env python3
"""Prepare disposable C3 signed A/B/N/recovery and matched S3 fixture apps.

Host-only: no serial, flash, OTA, reset, eFuse or commercial key operation.
Private RSA test keys remain in an explicit external directory and never enter
the report. The output is a candidate manifest, not physical qualification.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
EXPORT = Path(os.environ.get("GS_IDF_EXPORT", str(Path.home() / ".espressif/v6.0.3/esp-idf/export.sh")))


def outside_repo(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.is_relative_to(REPO.resolve()):
        raise ValueError("test private keys must be outside the repository")
    return resolved


def keys(directory: Path, generate: bool) -> tuple[Path, Path]:
    directory = outside_repo(directory)
    if not directory.exists():
        if not generate:
            raise ValueError("external key directory is absent; use --generate-test-keys")
        directory.mkdir(parents=True, mode=0o700)
    if directory.stat().st_mode & 0o077:
        raise ValueError("external key directory must have mode 0700")
    result = (directory / "gs114-p9-trusted.pem", directory / "gs114-p9-negative.pem")
    for path in result:
        if path.exists():
            if path.stat().st_mode & 0o077:
                raise ValueError("external test key must have mode 0600")
            continue
        if not generate:
            raise ValueError("test key is absent; use --generate-test-keys")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA",
                            "-pkeyopt", "rsa_keygen_bits:3072", "-out", str(path)],
                           check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except Exception:
            path.unlink(missing_ok=True)
            raise
    if result[0].samefile(result[1]):
        raise ValueError("trusted and negative test keys must differ")
    return result


def activated(args: list[str], log: Path, redact: tuple[Path, Path]) -> None:
    command = "source " + shlex.quote(str(EXPORT)) + " >/dev/null 2>&1 && " + shlex.join(args)
    result = subprocess.run(["bash", "-c", command], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=3600)
    output = result.stdout
    for secret_path in redact:
        output = output.replace(str(secret_path), "<external-test-key>")
    log.write_text(output)
    if result.returncode:
        raise RuntimeError(f"host artifact step failed, exit={result.returncode}; see {log}")


def prepare(key_dir: Path, generate: bool) -> Path:
    if not EXPORT.is_file():
        raise RuntimeError("ESP-IDF 6.0.3 activation is unavailable")
    trusted, negative = keys(key_dir, generate)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / "build/gs114_p9_signed" / stamp
    output.mkdir(parents=True, exist_ok=False)
    versions = {label: f"gs114{label}-{stamp[2:15]}" for label in ("A", "B", "N", "R")}
    records: dict[str, dict] = {}
    build_dir = str(ROOT / "build/gs114_p9_signed_build" / stamp)
    for label in ("A", "B", "N", "R"):
        image = output / f"c3-{label.lower()}.signed.bin"
        args = ["python", "scripts/build_signed_c3.py", "--signing-key",
                str(negative if label == "N" else trusted),
                "--version", versions[label], "--output", str(image),
                "--build-dir", build_dir, "--hil-control", "--physical-wake"]
        if label == "N":
            args += ["--trusted-key", str(trusted)]
        activated(args, output / f"build_c3_{label.lower()}.log", (trusted, negative))
        record = json.loads(image.with_suffix(image.suffix + ".json").read_text())
        if record.get("physical_wake") is not True or record.get("hil_control") is not True or \
                record.get("sha256") != hashlib.sha256(image.read_bytes()).hexdigest():
            raise RuntimeError(f"C3 {label} signed profile/provenance mismatch")
        records[label] = {"version": record["version"], "sha256": record["sha256"],
                          "size": record["size"], "profile": record["profile"],
                          "physical_wake": True,
                          "public_key_fingerprint_sha256": record["signing_public_key_fingerprint_sha256"],
                          "image": str(image)}
    if not (records["A"]["public_key_fingerprint_sha256"] ==
            records["B"]["public_key_fingerprint_sha256"] ==
            records["R"]["public_key_fingerprint_sha256"]):
        raise RuntimeError("A/B/recovery signing continuity failed")
    if records["N"]["public_key_fingerprint_sha256"] == records["A"]["public_key_fingerprint_sha256"]:
        raise RuntimeError("negative signer unexpectedly trusted")
    hubs: dict[str, dict] = {}
    s3_build_name = f"gs114p9N-{stamp[2:15]}"
    for label in ("N", "B", "R"):
        image = output / f"hub-{label.lower()}.bin"
        args = ["python", "scripts/build_secure_fota_hub.py", "--s3-fixture",
                "--node-image", records[label]["image"], "--output", str(image),
                "--label", f"gs114p9{label}-{stamp[2:15]}"]
        if label != "N":
            args += ["--build-dir", s3_build_name]
        activated(args, output / f"build_s3_{label.lower()}.log", (trusted, negative))
        record = json.loads(image.with_suffix(image.suffix + ".json").read_text())
        if record.get("embedded_c3_sha256") != records[label]["sha256"] or \
                record.get("profile") != "gs114-s3-signed-fota-fixture":
            raise RuntimeError(f"S3 {label} embedded-image provenance mismatch")
        hubs[label] = {"image": str(image), "sha256": record["hub_sha256"],
                       "size": record["hub_size"], "embedded_c3_sha256": record["embedded_c3_sha256"]}
    manifest = {"schema": 1, "owner": "GS-114 P9-B", "source_head": subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, check=True, capture_output=True,
        text=True).stdout.strip(), "source_dirty": bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO, check=True, capture_output=True,
        text=True).stdout.strip()), "images": records, "hubs": hubs,
        "private_keys": "EXTERNAL_TEST_ONLY_NOT_RECORDED",
        "hardware_operations": "NONE", "physical_status": "NOT_RUN"}
    target = output / "gs114_p9_artifacts.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-dir", type=Path, required=True,
                        help="external 0700 directory for disposable RSA-3072 test keys")
    parser.add_argument("--generate-test-keys", action="store_true",
                        help="create absent test-only keys in the external directory")
    args = parser.parse_args()
    try:
        print("GS114 P9 HOST ARTIFACT MANIFEST", prepare(args.key_dir, args.generate_test_keys))
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"GS114 P9 HOST ARTIFACTS FAIL: {error}\n")
