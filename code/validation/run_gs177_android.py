#!/usr/bin/env python3
"""Build and verify the GS-177 branded, configured connected Lite APK."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "parivar_saathi_android_app" / "android"
APK = PROJECT / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
TEST_RESULTS = PROJECT / "app" / "build" / "test-results" / "testDebugUnitTest"
SDK_ROOT = Path(os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME", ""))
BUILD_TOOLS = SDK_ROOT / "build-tools" / "35.0.0"
EXPECTED_TEST_SIGNER = PROJECT / "app" / "gs179_discovery_test_signer_sha256.txt"
BRANDING_SCRIPT = ROOT / "parivar_saathi_android_app/branding/generate_parivar_saathi_assets.py"
BRANDING_SOURCE = ROOT / "parivar_saathi_android_app/branding/source/Parivar_Saathi_Logo.png"
BRANDING_SOURCE_SHA256 = "d0ff244d61b5cb047c320fc3af1028fa8e780186189a481657b8fea14b679441"


def run(command: list[str], *, cwd: Path, emit_output: bool = True) -> tuple[int, str]:
    print("COMMAND:", " ".join(command), flush=True)
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError as error:
        print(f"GS177 ANDROID DASHBOARD BLOCKED dependency={error.filename}", flush=True)
        return 127, ""
    if emit_output:
        print(result.stdout, end="", flush=True)
    return result.returncode, result.stdout


def junit_counts() -> tuple[int, int, int, int]:
    files = sorted(TEST_RESULTS.glob("TEST-*.xml"))
    tests = failures = errors = skipped = 0
    for path in files:
        root = ET.parse(path).getroot()
        tests += int(root.attrib.get("tests", "0"))
        failures += int(root.attrib.get("failures", "0"))
        errors += int(root.attrib.get("errors", "0"))
        skipped += int(root.attrib.get("skipped", "0"))
    return tests, failures, errors, skipped


def png_dimensions(path: Path) -> tuple[int, int, int]:
    data = path.read_bytes()
    if len(data) < 26 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"invalid PNG: {path}")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
    return width, height, color_type


def validate_branding(app_root: Path, app_pwa: Path) -> tuple[bool, str]:
    if not BRANDING_SOURCE.is_file() or hashlib.sha256(BRANDING_SOURCE.read_bytes()).hexdigest() != BRANDING_SOURCE_SHA256:
        return False, "approved_logo_provenance_mismatch"
    check = subprocess.run(
        [sys.executable, str(BRANDING_SCRIPT), "--check"],
        cwd=ROOT.parent,
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode:
        return False, "generated_branding_assets_missing: " + check.stdout.strip()

    res = app_root / "android/app/src/main/res"
    expected_pngs = {
        res / "drawable-nodpi/ic_launcher_foreground.png": (432, 432, 6),
        res / "drawable-nodpi/ic_launcher_monochrome.png": (432, 432, 6),
        res / "drawable-nodpi/ic_stat_parivar_saathi.png": (96, 96, 6),
        res / "drawable-xhdpi/parivar_saathi_splash_wordmark.png": (720, 195, 6),
        app_pwa / "assets/parivar-saathi-icon-192.png": (192, 192, 6),
        app_pwa / "assets/parivar-saathi-icon-maskable-512.png": (512, 512, 6),
    }
    for density, size in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        expected_pngs[res / f"mipmap-{density}/ic_launcher.png"] = (size, size, 6)
        expected_pngs[res / f"mipmap-{density}/ic_launcher_round.png"] = (size, size, 6)
    try:
        for path, expected in expected_pngs.items():
            if png_dimensions(path) != expected:
                return False, f"invalid_brand_asset_dimensions:{path.relative_to(ROOT)}"
        for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
            root = ET.parse(res / f"mipmap-anydpi-v26/{name}").getroot()
            tags = {child.tag for child in root}
            if root.tag != "adaptive-icon" or not {"background", "foreground", "monochrome"} <= tags:
                return False, f"adaptive_icon_layers_missing:{name}"
        manifest = ET.parse(app_root / "android/app/src/main/AndroidManifest.xml").getroot()
        application = manifest.find("application")
        android_ns = "{http://schemas.android.com/apk/res/android}"
        if application is None or application.attrib.get(android_ns + "icon") != "@mipmap/ic_launcher":
            return False, "launcher_icon_not_configured"
        if application.attrib.get(android_ns + "roundIcon") != "@mipmap/ic_launcher_round":
            return False, "round_launcher_icon_not_configured"
        if application.attrib.get(android_ns + "theme") != "@style/Theme.ParivarSaathi.Starting":
            return False, "branded_starting_theme_not_configured"
        strings = ET.parse(res / "values/strings.xml").getroot()
        app_name = next((node.text for node in strings.findall("string") if node.attrib.get("name") == "app_name"), None)
        if app_name != "Parivar Saathi":
            return False, "android_app_label_mismatch"
        styles = (res / "values/styles.xml").read_text()
        activity = (app_root / "android/app/src/main/java/in/gharsajag/caregiver/MainActivity.kt").read_text()
        if 'name="android:windowSplashScreenBrandingImage"' not in styles or "parivar_saathi_splash_wordmark" not in styles:
            return False, "complete_logo_missing_from_splash"
        if "installSplashScreen()" not in activity:
            return False, "splashscreen_api_not_installed"
        web_manifest = json.loads((app_pwa / "manifest.webmanifest").read_text())
        icon_entries = {(entry.get("sizes"), entry.get("purpose")) for entry in web_manifest.get("icons", [])}
        if web_manifest.get("name") != "Parivar Saathi" or not {
            ("192x192", "any"), ("512x512", "any maskable")
        } <= icon_entries:
            return False, "pwa_brand_or_icon_manifest_mismatch"
        if "parivar-saathi-icon-192.png" not in (app_pwa / "assets/icon.svg").read_text():
            return False, "legacy_pwa_icon_not_aligned_with_approved_logo"
    except (OSError, ValueError, ET.ParseError, json.JSONDecodeError) as error:
        return False, f"branding_validation_error:{error}"
    print("CASE GS177-ANDROID-BRANDING-001 PASS", flush=True)
    return True, ""


def main() -> int:
    gradle = shutil.which("gradle")
    node = shutil.which("node")
    if not node:
        print("GS177 ANDROID BLOCKED dependency=node", flush=True)
        return 127

    app_root = ROOT / "parivar_saathi_android_app"
    app_pwa = ROOT / "tools" / "sim" / "pwa"
    main_activity = (app_root / "android/app/src/main/java/in/gharsajag/caregiver/MainActivity.kt").read_text()
    gradle_build = (app_root / "android/app/build.gradle.kts").read_text()
    endpoint_store = (app_root / "android/app/src/main/java/in/gharsajag/caregiver/BackendEndpointStore.kt").read_text()
    lan_discovery = (app_root / "android/app/src/main/java/in/gharsajag/caregiver/Gs179LanDiscovery.kt").read_text()
    lan_discovery_tests = (app_root / "android/app/src/test/java/in/gharsajag/caregiver/Gs179LanDiscoveryPolicyTest.kt").read_text()
    pairing_action = main_activity.split("private fun usePairedLaptop()", 1)[1].split(
        "private fun lanDiagnostic(", 1,
    )[0]
    windows_mdns = (ROOT / "tools/local/gs179-windows-mdns-advertiser.ps1").read_text()
    local_lan_manifest = (app_root / "android/app/src/gs179LocalLan/AndroidManifest.xml").read_text()
    trusted_webview = (app_root / "android/app/src/main/java/in/gharsajag/caregiver/TrustedPwaWebView.kt").read_text()
    origin_tests = (app_root / "android/app/src/test/java/in/gharsajag/caregiver/BackendOriginTest.kt").read_text()
    if "showSetup" in main_activity or "HTTPS server address" in main_activity:
        print("GS177 ANDROID DASHBOARD FAIL legacy_manual_setup_screen_present", flush=True)
        return 1
    if ("BuildConfig.GS179_LOCAL_LAN_TEST_ONLY" not in main_activity or
            "BackendOrigin.parse(" not in main_activity or
            "BackendEndpointStore.save(this, candidate)" not in main_activity or
            "BackendEndpointStore.load(this)" not in main_activity or
            "BackendEndpointStore.clear(this)" not in main_activity or
            "currentEndpointRetained=true" not in pairing_action or
            "BackendEndpointStore.clear" in pairing_action or
            "backendOrigin = pairedOrigin" in pairing_action or
            "usePairedLaptop()" not in main_activity or
            "BuildConfig.GS179_LOCAL_LAN_TEST_ONLY" not in endpoint_store or
            "gs177AndroidLanReconnectStableMdnsHostnameAndManualPrivateAddressAreTestOnly" not in origin_tests or
            "gs177AndroidLanReconnectIsReachableOnlyFromBundledFirstPartyMainFrame" not in origin_tests or
            "handler.cancel()" not in trusted_webview or
            "ConnectivityManager.NetworkCallback" not in main_activity or
            "onLinkPropertiesChanged" not in main_activity or
            "wifiRouteSignature" not in main_activity or
            "shouldReloadForVerifiedEndpoint" not in main_activity or
            "NsdManager.PROTOCOL_DNS_SD" not in lan_discovery or
            "DISCOVERY_STARTED" not in lan_discovery or
            "DISCOVERY_NO_EXPECTED_SERVICE_FOUND" not in lan_discovery or
            "DISCOVERY_DIAGNOSTIC_TIMER_FAILED" not in lan_discovery or
            "SERVICE_FOUND" not in lan_discovery or
            "unexpected_service_type" not in lan_discovery or
            "SERVICE_RESOLVE_FAILED" not in lan_discovery or
            "serviceMismatchReason" not in lan_discovery or
            "persistence_failure" not in lan_discovery or
            "main_handler_rejected" not in lan_discovery or
            "no_private_ipv4" not in lan_discovery or
            "saved_spki_pin_mismatch" not in lan_discovery or
            "readyz_database_not_ready" not in lan_discovery or
            "hostAddresses" not in lan_discovery or
            "HttpsURLConnection" not in lan_discovery or
            "serverCertificates" not in lan_discovery or
            "certificateNamesExpectedHost" not in lan_discovery or
            "serverSpkiSha256" not in lan_discovery or
            "saveVerifiedLanServer" not in lan_discovery or
            "Gs179LanDiscoveryPolicy.isPrivateIpv4(origin.host)" not in endpoint_store or
            "MAX_PROBE_ADDRESSES = 4" not in lan_discovery or
            "MAX_PENDING_RESOLVES = 2" not in lan_discovery or
            "MAX_READY_BYTES = 4096" not in lan_discovery or
            "connection.connectTimeout = TIMEOUT_MILLIS" not in lan_discovery or
            "connection.readTimeout = TIMEOUT_MILLIS" not in lan_discovery or
            "connection.instanceFollowRedirects = false" not in lan_discovery or
            "GS177-LAN-NSD-001" not in lan_discovery_tests or
            "GS179-LAN-DIAGNOSTICS-001" not in lan_discovery_tests or
            "verifiedSameOriginReconnectsOnlyAfterWifiRouteChanges" not in lan_discovery_tests or
            "selectsEveryPrivateIpv4AndRejectsPublicIpv4AndIpv6Candidates" not in lan_discovery_tests or
            "tlsDiagnosticReasonsDistinguishTimeoutHostnameAndOtherHandshakeFailures" not in lan_discovery_tests or
            "DnsServiceRegister" not in windows_mdns or
            "ToIp4AddressHostOrder" not in windows_mdns or
            "HasExpectedIp4HostOrder" not in windows_mdns or
            "REGISTER_CALLBACK_FAILED_status_" not in windows_mdns or
            "registercallbackstatus" not in windows_mdns.lower() or
            "Ip4AddressHostByteOrder = \"PASS\"" not in windows_mdns or
            "Action -eq \"Status\"" not in windows_mdns or
            "REGISTER_FAILED" not in windows_mdns or
            "UnicastEnabled = false" not in windows_mdns or
            "Test-TrustedWifiProfile" not in windows_mdns or
            '@("Private", "DomainAuthenticated")' not in windows_mdns or
            "PersistentPrivilegedTaskRegistered = $false" not in windows_mdns or
            "android.permission.ACCESS_NETWORK_STATE" not in local_lan_manifest or
            "android.permission.ACCESS_WIFI_STATE" not in local_lan_manifest or
            "android.permission.CHANGE_WIFI_MULTICAST_STATE" not in local_lan_manifest):
        print("GS177 ANDROID DASHBOARD FAIL secure_TEST_ONLY_reconnect_flow_missing", flush=True)
        return 1
    print("CASE GS177-LAN-NSD-001 SOURCE_PASS", flush=True)
    required_pwa = [
        "index.html", "app.js", "connected_lite.mjs", "password_visibility.mjs", "caregiver.css",
        "runtime_mode.mjs", "styles.css",
        "assets/parivar-saathi-icon-192.png",
        "assets/parivar-saathi-icon-maskable-512.png", "assets/icon.svg",
    ]
    if any(not (app_pwa / relative).is_file() for relative in required_pwa):
        print("GS177 ANDROID DASHBOARD FAIL shared_pwa_source_incomplete", flush=True)
        return 1
    if 'getByName("release")' not in gradle_build or 'DEV_ENDPOINT_CONFIG_ALLOWED", "false"' not in gradle_build:
        print("GS177 ANDROID DASHBOARD FAIL release_dev_override_policy_missing", flush=True)
        return 1
    backend_origin = os.environ.get("GS177_BACKEND_ORIGIN", "")
    local_lan_test_only = os.environ.get("GS177_LOCAL_LAN_TEST_ONLY", "0")
    if local_lan_test_only not in {"0", "1"}:
        print("GS177 ANDROID BUILD FAIL invalid_local_lan_profile", flush=True)
        return 1
    if not backend_origin:
        print("GS177 ANDROID BUILD BLOCKED dependency=approved_hosted_backend_origin", flush=True)
        return 127
    if local_lan_test_only == "1":
        if ('"in.gharsajag.caregiver.discoverytest"' not in gradle_build or
                '"in.gharsajag.caregiver"' not in gradle_build or
                "GS179_DISCOVERY_TEST_KEYSTORE_PATH" not in gradle_build or
                "GS179_DISCOVERY_TEST_KEYSTORE_PASSWORD" not in gradle_build or
                "gs179DiscoveryTest" not in gradle_build):
            print("GS177 ANDROID BUILD FAIL side_by_side_TEST_ONLY_identity_missing", flush=True)
            return 1
        if not EXPECTED_TEST_SIGNER.is_file() or not re.fullmatch(
                r"[0-9a-f]{64}", EXPECTED_TEST_SIGNER.read_text(encoding="ascii").strip()):
            print("GS177 ANDROID BUILD FAIL persistent_TEST_ONLY_signer_fingerprint_missing", flush=True)
            return 1
        try:
            parsed = urlsplit(backend_origin)
            host = parsed.hostname or ""
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
        except ValueError:
            address = None
            parsed = None
            host = ""
        private_ip = isinstance(address, ipaddress.IPv4Address) and any(
            address in network for network in (
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
            )
        )
        local_hostname = bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.local", host))
        if (not (private_ip or local_hostname) or parsed is None or parsed.scheme != "https" or
                parsed.netloc != parsed.hostname or
                parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            print("GS177 ANDROID BUILD FAIL LAN_TEST_ONLY_requires_exact_private_or_local_HTTPS_origin", flush=True)
            return 1
        local_profile = PROJECT / "app/src/gs179LocalLan"
        ca_path = local_profile / "res/raw/gs179_local_lan_test_ca.pem"
        manifest_path = local_profile / "AndroidManifest.xml"
        trust_path = local_profile / "res/xml/network_security_config.xml"
        if not ca_path.is_file() or not manifest_path.is_file() or not trust_path.is_file():
            print("GS177 ANDROID BUILD FAIL LAN_TEST_ONLY_CA_missing", flush=True)
            return 1
        try:
            manifest = ET.parse(manifest_path).getroot()
            application = manifest.find("application")
            android_ns = "{http://schemas.android.com/apk/res/android}"
            trust_config = ET.parse(trust_path).getroot()
            base_config = trust_config.find("base-config")
            ca_text = ca_path.read_text(encoding="ascii")
        except (OSError, ET.ParseError, UnicodeError) as error:
            print(f"GS177 ANDROID BUILD FAIL invalid_LAN_TEST_ONLY_trust_profile:{error}", flush=True)
            return 1
        openssl = shutil.which("openssl")
        if not openssl:
            print("GS177 ANDROID BUILD BLOCKED dependency=openssl_for_LAN_CA_validation", flush=True)
            return 127
        ca_result = subprocess.run(
            [openssl, "x509", "-in", str(ca_path), "-noout", "-subject", "-issuer", "-text", "-checkend", "0"],
            check=False, capture_output=True, text=True,
        )
        ca_output = ca_result.stdout
        subject = next((line.partition("=")[2].strip() for line in ca_output.splitlines()
                        if line.startswith("subject=")), "")
        issuer = next((line.partition("=")[2].strip() for line in ca_output.splitlines()
                       if line.startswith("issuer=")), "")
        if (ca_result.returncode != 0 or not subject or subject != issuer or
                not re.search(r"X509v3 Basic Constraints: critical\s+CA:TRUE", ca_output) or
                not re.search(r"X509v3 Key Usage: critical\s+Certificate Sign, CRL Sign", ca_output)):
            print("GS177 ANDROID BUILD FAIL LAN_TEST_ONLY_anchor_must_be_current_self_signed_CA", flush=True)
            return 1
        has_test_ca = any(
            node.attrib.get("src") == "@raw/gs179_local_lan_test_ca"
            for group in ([base_config] if base_config is not None else [])
            for anchors in group.findall("trust-anchors")
            for node in anchors.findall("certificates")
        )
        if (application is None or
                application.attrib.get(android_ns + "networkSecurityConfig") != "@xml/network_security_config" or
                base_config is None or base_config.attrib.get("cleartextTrafficPermitted") != "false" or
                not has_test_ca or "-----BEGIN CERTIFICATE-----" not in ca_text or
                "-----END CERTIFICATE-----" not in ca_text):
            print("GS177 ANDROID BUILD FAIL origin_not_exactly_bound_to_CA_pinned_LAN_profile", flush=True)
            return 1

    valid, failure = validate_branding(app_root, app_pwa)
    if not valid:
        print(f"GS177 ANDROID BRANDING FAIL {failure}", flush=True)
        return 1

    rc, runtime_output = run([node, "--test", "tests/js/caregiver_runtime.test.mjs"], cwd=ROOT)
    if rc:
        print(f"GS177 PWA RUNTIME FAIL exit={rc}", flush=True)
        return rc
    if not re.search(r"(?m)^ok \d+ - GS177-PWA-LAN-RECONNECT-001\b", runtime_output):
        print("GS177 PWA RUNTIME FAIL LAN_reconnect_test_not_reported", flush=True)
        return 1
    print("CASE GS177-PWA-LAN-RECONNECT-001 PASS", flush=True)
    print("CASE GS177-PWA-RUNTIME-001 PASS", flush=True)

    if not gradle:
        print("GS177 ANDROID BUILD BLOCKED dependency=gradle", flush=True)
        return 127
    if not os.environ.get("ANDROID_SDK_ROOT") and not os.environ.get("ANDROID_HOME"):
        print("GS177 ANDROID BUILD BLOCKED dependency=ANDROID_SDK_ROOT_OR_ANDROID_HOME", flush=True)
        return 127

    rc, gradle_output = run(
        [gradle, "--no-daemon", "--stacktrace", "--console=plain",
         f"-PcaregiverDebugBackendOrigin={backend_origin}",
         f"-Pgs179LocalLanTestOnly={str(local_lan_test_only == '1').lower()}",
         ":app:testDebugUnitTest", ":app:assembleDebug"],
        cwd=PROJECT,
        emit_output=False,
    )
    if rc:
        diagnostics = [
            line.strip()
            for line in gradle_output.splitlines()
            if re.search(r"(?:^e: |\berror:|^FAILURE:|^Execution failed for task)", line)
        ]
        if diagnostics:
            print("GS177 ANDROID DASHBOARD DIAGNOSTICS:", flush=True)
            for line in diagnostics[-20:]:
                print(f"GS177 ANDROID DIAGNOSTIC {line}", flush=True)
        print(f"GS177 ANDROID DASHBOARD FAIL gradle_exit={rc}", flush=True)
        return rc

    tests, failures, errors, skipped = junit_counts()
    if tests < 1 or failures or errors or skipped:
        print(
            f"GS177 ANDROID DASHBOARD FAIL junit_tests={tests} failures={failures} errors={errors} skipped={skipped}",
            flush=True,
        )
        return 1
    print("CASE GS177-ANDROID-LAN-RECONNECT-001 PASS", flush=True)
    if not APK.is_file():
        print(f"GS177 ANDROID DASHBOARD FAIL apk_missing={APK}", flush=True)
        return 1

    expected_package = (
        "in.gharsajag.caregiver.discoverytest"
        if local_lan_test_only == "1"
        else "in.gharsajag.caregiver"
    )
    rc, package_output = run(
        [str(BUILD_TOOLS / "aapt"), "dump", "badging", str(APK)],
        cwd=PROJECT,
        emit_output=False,
    )
    package_match = re.search(r"(?m)^package: name='([^']+)'", package_output)
    expected_label = (
        "Parivar Saathi TEST_ONLY"
        if local_lan_test_only == "1"
        else "Parivar Saathi"
    )
    label_match = re.search(r"(?m)^application-label:'([^']+)'", package_output)
    if (rc or not package_match or package_match.group(1) != expected_package or
            not label_match or label_match.group(1) != expected_label):
        print(
            f"GS177 ANDROID DASHBOARD FAIL apk_identity_mismatch expected_package={expected_package}",
            flush=True,
        )
        return 1
    print(
        f"CASE GS177-ANDROID-PACKAGE-ID-001 PASS package={expected_package} label={expected_label}",
        flush=True,
    )

    if local_lan_test_only == "1":
        rc, signature_output = run(
            [str(BUILD_TOOLS / "apksigner"), "verify", "--verbose", "--print-certs", str(APK)],
            cwd=PROJECT,
            emit_output=False,
        )
        match = re.search(
            r"(?mi)^Signer #1 certificate SHA-256 digest:\s*([0-9a-f]{64})\s*$",
            signature_output,
        )
        signer_sha256 = match.group(1).lower() if match else ""
        expected_sha256 = EXPECTED_TEST_SIGNER.read_text(encoding="ascii").strip()
        if rc or signer_sha256 != expected_sha256:
            print("GS177 ANDROID DASHBOARD FAIL persistent_TEST_ONLY_signer_mismatch", flush=True)
            return 1
        print(f"CASE GS179-DISCOVERYTEST-SIGNER-001 PASS sha256={signer_sha256}", flush=True)
    else:
        print("CASE GS179-DISCOVERYTEST-SIGNER-001 NOT_APPLICABLE production_profile", flush=True)

    required_assets = {
        "assets/index.html",
        "assets/app.js",
        "assets/boot.mjs",
        "assets/connected_lite.mjs",
        "assets/password_visibility.mjs",
        "assets/caregiver.css",
        "assets/runtime_mode.mjs",
        "assets/styles.css",
        "assets/assets/parivar-saathi-icon-192.png",
        "assets/assets/parivar-saathi-icon-maskable-512.png",
        "assets/assets/icon.svg",
    }
    try:
        with zipfile.ZipFile(APK) as apk:
            bundled_assets = set(apk.namelist())
            source_bound_assets = (
                "index.html", "boot.mjs", "connected_lite.mjs", "password_visibility.mjs", "caregiver.css",
            )
            stale_or_mismatched = [
                relative for relative in source_bound_assets
                if apk.read(f"assets/{relative}") != (app_pwa / relative).read_bytes()
            ]
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        print(f"GS177 ANDROID DASHBOARD FAIL invalid_apk={error}", flush=True)
        return 1
    missing_assets = sorted(required_assets - bundled_assets)
    if missing_assets or stale_or_mismatched or "assets/runtime-config.js" in bundled_assets:
        print(
            f"GS177 ANDROID DASHBOARD FAIL shared_pwa_assets_missing={missing_assets} source_asset_mismatch={stale_or_mismatched} static_runtime_config={('assets/runtime-config.js' in bundled_assets)}",
            flush=True,
        )
        return 1

    required_resources = {
        "ic_launcher.xml", "ic_launcher_round.xml", "ic_launcher_foreground.png",
        "ic_launcher_monochrome.png", "ic_stat_parivar_saathi.png", "parivar_saathi_splash_wordmark.png",
        "ic_launcher.png", "ic_launcher_round.png",
    }
    present_resources = {Path(name).name for name in bundled_assets if name.startswith("res/")}
    if required_resources - present_resources:
        print(f"GS177 ANDROID DASHBOARD FAIL branding_resources_missing={sorted(required_resources - present_resources)}", flush=True)
        return 1

    apksigner = BUILD_TOOLS / "apksigner"
    if not apksigner.is_file():
        print(f"GS177 ANDROID DASHBOARD BLOCKED dependency={apksigner}", flush=True)
        return 127
    rc, _ = run([str(apksigner), "verify", "--verbose", str(APK)], cwd=PROJECT)
    if rc:
        print(f"GS177 ANDROID DASHBOARD FAIL apksigner_exit={rc}", flush=True)
        return rc

    digest = hashlib.sha256(APK.read_bytes()).hexdigest()
    print("CASE GS177-ANDROID-ORIGIN-001 PASS", flush=True)
    print("CASE GS177-ANDROID-PWA-BUNDLE-001 PASS", flush=True)
    print(f"GS177 ANDROID DASHBOARD PASS tests={tests} skipped={skipped} apk_sha256={digest}", flush=True)
    print(f"APK={APK.relative_to(ROOT)}", flush=True)
    print(f"SOURCE_REVISION={os.environ.get('GITHUB_SHA', 'local')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
