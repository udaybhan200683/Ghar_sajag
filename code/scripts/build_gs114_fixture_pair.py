#!/usr/bin/env python3
"""Build a disposable C3/S3 GS-114 pair; no serial or hardware access."""
from pathlib import Path
import hashlib, json, os, shlex, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation.component_gate import source_fingerprint


def build(export: Path, project: Path, build_dir: Path, sdkconfig: Path,
          target: str, name: str, version: str, options: list[str]) -> Path:
    args = ["idf.py", "-C", str(project), "-B", str(build_dir),
            "-D", "SDKCONFIG=" + str(sdkconfig), "-D", "IDF_TARGET=" + target,
            "-D", "PROJECT_VER=" + version, "-D", "GS_HIL_BUILD=OFF"]
    args.extend(options)
    args.extend(["build", "size"])
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


def main() -> int:
    export = Path(os.environ.get("GS_IDF_EXPORT", str(Path.home() / ".espressif/v6.0.3/esp-idf/export.sh")))
    if not export.is_file():
        raise RuntimeError("ESP-IDF 6.0.3 activation missing: " + str(export))
    out = ROOT / "build/gs114_fixture_pair"
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="build-", dir=out))
    fingerprint = source_fingerprint(extra=["scripts/build_gs114_fixture_pair.py"])
    head = subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, text=True).strip()
    version = f"{head}-gs114-{fingerprint[:8]}"
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
    s3 = build(export, s3_project, work / "s3", work / "s3-sdkconfig", "esp32s3", "s3", version,
               ["-D", "GS_HIL_CONTROL=OFF", "-D", "GS_HIL_COMMISSIONING=ON",
                "-D", "SDKCONFIG_DEFAULTS=" + str(s3_project / "sdkconfig.defaults") + ";" + str(s3_project / "sdkconfig.defaults.outbox"),
                "-D", "GS_NODE_FIRMWARE_ASSET=" + str(asset)])
    result = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_fingerprint": fingerprint, "idf": "6.0.3", "profile": "GS-114 disposable fixture; C3 HIL_CONTROL/physical wake; S3 commissioning-only",
        "artifacts": {}, "hardware_actions": "NONE", "physical_status": "NOT_RUN",
    }
    for role, image in (("c3", c3), ("s3", s3)):
        data = image.read_bytes()
        result["artifacts"][role] = {"path": str(image), "bytes": len(data),
                                      "sha256": hashlib.sha256(data).hexdigest()}
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
