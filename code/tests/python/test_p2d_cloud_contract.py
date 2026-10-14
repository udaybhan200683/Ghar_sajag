"""Real SQLite transactions + Hub HTTP parser and durable completion/reboot.

The stdio channel is a deterministic fixture, NOT TLS or a live deployment.
It injects authenticated-channel evidence after invoking the real API trust seam.
"""
import copy
import json
import os
import selectors
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from ghar_sajag.database import initialize_sqlite
from ghar_sajag.durable_commit import DurableEventCommit
from ghar_sajag.durable_api import open_durable_event_api
from ghar_sajag.http_api import JsonApi
from ghar_sajag.model import Resident
from ghar_sajag.ownership_registry import (
    AuthorizedHomeOperation,
    VerifiedHubIdentity,
    VerifiedNodeEnrollment,
)
from ghar_sajag.service import GharSajagService


class P2DCloudContractTest(unittest.TestCase):
    def test_worker_api_registered_ownership_lost_reply_retry_and_projection(self):
        binary = os.environ.get("P2D_TEST_BINARY", str(ROOT / "build/p2d_cloud_contract_validation"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "worker-api.sqlite"

            def open_api(seed=False):
                service = GharSajagService()
                service.homes.create("home-a", "Fixture", "Asia/Kolkata", "en-IN", "care-1",
                                     [Resident("resident-1", "Resident", True, 1)], 1)
                composed = open_durable_event_api(
                    service, path, now=lambda: 1800000999,
                    require_registered_ownership=True)
                if seed:
                    with composed.db:
                        for home in ("home-a", "home-b"):
                            composed.db.execute(
                                "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?, 'UTC',1,1)",
                                (home, "Fixture"),
                            )
                        composed.db.execute(
                            "INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES('care-1','Caregiver',1)")
                        composed.db.execute(
                            "INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES('home-a','care-1','PRIMARY')")
                    registry = composed.api.hub_ownership_registry
                    identity = VerifiedHubIdentity("hub-permanent-1", "a" * 64,
                                                   "fixture-hub-proof")
                    registry.register_unclaimed_identity(identity, 2)
                    registry.claim_home(identity,
                        AuthorizedHomeOperation("installer-a", "home-a", "CLAIM_HUB",
                                                "fixture-claim"), 3)
                    registry.enroll_node(identity,
                        AuthorizedHomeOperation("installer-a", "home-a", "ENROLL_NODE",
                                                "fixture-node-enrollment"),
                        VerifiedNodeEnrollment("device-room1", "room1", 3,
                                               "b" * 64, "fixture-node-proof"), 4)
                return service, composed

            service, endpoint = open_api(seed=True)
            process = subprocess.Popen([binary, "--worker-api-bridge"], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, bufsize=1)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            try:
                def read_bridge_line(message):
                    self.assertTrue(selector.select(timeout=20), message)
                    line = process.stdout.readline()
                    self.assertTrue(line, message + ": bridge exited")
                    return line.strip()

                first_body = json.loads(read_bridge_line("worker did not submit original event"))
                self.assertEqual(first_body["cloudsync_version"], 2)
                self.assertEqual(first_body["node_enrollment_generation"], 3)
                self.assertEqual(first_body["event_key"], {
                    "physical_device_id": "device-room1", "logical_node_id": "room1",
                    "origin_session_id": 42, "event_sequence": 1,
                })
                self.assertEqual((first_body["event_type"], first_body["occurred_at"],
                                  first_body["hub_received_at"]),
                                 ("CALL_FAMILY", 1800000001, 1800000901))
                context = {"gs.verified_hub": "hub-permanent-1",
                           "gs.hub_key_fingerprint": "a" * 64,
                           "gs.installation_epoch": 1}

                # Current registry policy rejects this exact original event
                # when the URL selects another Home or the Hub epoch is stale.
                with self.assertRaises(PermissionError):
                    endpoint.api.dispatch("POST", "/v1/homes/home-b/events", "",
                                          first_body, request_context=context)
                stale = dict(context, **{"gs.installation_epoch": 2})
                with self.assertRaises(PermissionError):
                    endpoint.api.dispatch("POST", "/v1/homes/home-a/events", "",
                                          first_body, request_context=stale)
                self.assertEqual(endpoint.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

                status, receipt = endpoint.api.dispatch(
                    "POST", "/v1/homes/home-a/events", "", first_body,
                    request_context=context)
                self.assertTrue(status.startswith("201"))
                self.assertEqual((receipt["status"], receipt["duplicate"]), ("COMMITTED", False))
                independent = sqlite3.connect(path)
                self.assertEqual(independent.execute(
                    "SELECT COUNT(*) FROM durable_event_commits WHERE home_id='home-a' AND physical_device_id='device-room1' AND logical_node_id='room1' AND origin_session_id=42 AND event_sequence=1"
                ).fetchone()[0], 1)
                independent.close()
                # The simulated HTTP response is lost after the real DB commit.
                process.stdin.write("0 0 0\n{}\n")
                process.stdin.flush()
                endpoint.close()

                service, endpoint = open_api()
                retry_body = json.loads(read_bridge_line("worker did not retry after lost response"))
                self.assertEqual(retry_body, first_body, "worker changed immutable EventKey/body on retry")
                retry_status, retry_receipt = endpoint.api.dispatch(
                    "POST", "/v1/homes/home-a/events", "", retry_body,
                    request_context=context)
                self.assertTrue(retry_status.startswith("200"))
                self.assertEqual((retry_receipt["status"], retry_receipt["duplicate"]),
                                 ("COMMITTED", True))
                process.stdin.write("200 1 1\n" + json.dumps(retry_receipt, separators=(",", ":")) + "\n")
                process.stdin.flush()
                result = read_bridge_line("worker did not report completed durable retry")
                self.assertIn("RESULT gs148_worker_api_bridge=PASS completed=1 attempts=2", result)
                self.assertEqual(process.wait(timeout=10), 0, process.stderr.read())

                for table in ("events", "durable_event_commits", "alerts", "notification_jobs",
                              "durable_notification_outbox"):
                    self.assertEqual(endpoint.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                                     1, table + " must have one logical effect")
                projection = service.queries.snapshot("home-a", "care-1", 1800001000)
                self.assertEqual(projection["recent_events"][0]["kind"], "CALL_FAMILY")
                self.assertEqual(projection["recent_events"][0]["occurred_at"], 1800000001)
                print("GS148-CLOUD-WORKER-API-001 PASS retry_same_event=1 durable_effects=1 caregiver_projection=1")
            finally:
                selector.close()
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                process.stdin.close()
                process.stdout.close()
                process.stderr.close()
                endpoint.close()

    def test_real_commit_lost_reply_partial_catchup_reboots(self):
        binary = os.environ.get("P2D_TEST_BINARY", str(ROOT / "build/p2d_cloud_contract_validation"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backend.sqlite"
            def connect():
                db = sqlite3.connect(path)
                initialize_sqlite(db)
                db.execute("PRAGMA synchronous=FULL")
                return db
            db = connect()
            with db:
                db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-1','Fixture','UTC',1,1)")
                db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES('care-1','Fixture',1)")
                db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES('home-1','care-1','PRIMARY')")
            def api():
                return JsonApi(durable_events=DurableEventCommit(db), now=lambda: 1800000999,
                               authorize_hub=lambda context, home, key:
                               context.get("gs.verified_hub") == "fixture-hub" and
                               home == "home-1" and isinstance(key, dict) and
                               key.get("physical_device_id") == "device-" + key.get("logical_node_id", "") and
                               key.get("logical_node_id") in {f"room{i}" for i in range(6)})
            endpoint = api()
            process = subprocess.Popen([binary, "--bridge"], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            start = time.monotonic()
            original = {}
            attempts = duplicates = failures = restarts = 0
            output = None
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            try:
                while True:
                    self.assertTrue(selector.select(timeout=90), "Hub bridge stalled")
                    line = process.stdout.readline()
                    if not line:
                        self.fail("Hub bridge ended unexpectedly: " + process.stderr.read())
                    if line.startswith("RESULT "):
                        output = line.strip()
                        break
                    body = json.loads(line)
                    key = tuple(body["event_key"].values())
                    if key in original:
                        self.assertEqual(body, original[key], "original content/time changed on retry")
                    else:
                        original[key] = copy.deepcopy(body)
                    status, authenticated, complete, response = 0, 1, 1, {}
                    if attempts == 0:
                        # A client-controlled actor header is never Hub auth.
                        with self.assertRaises(PermissionError):
                            endpoint.dispatch("POST", "/v1/homes/home-1/events", "fixture-hub", body,
                                              request_context={"HTTP_X_ACTOR_ID": "fixture-hub"})
                        status, response = 403, {"error": "hub_not_authorized"}
                        failures += 1
                    else:
                        result_status, response = endpoint.dispatch(
                            "POST", "/v1/homes/home-1/events", "", body,
                            request_context={"gs.verified_hub": "fixture-hub"})
                        status = int(result_status[:3])
                        self.assertEqual(response["status"], "COMMITTED")
                        duplicates += int(response["duplicate"])
                        # The row must be visible on an independent connection
                        # before any response reaches the Hub.
                        verification = sqlite3.connect(path)
                        self.assertEqual(verification.execute(
                            "SELECT COUNT(*) FROM durable_event_commits WHERE physical_device_id=? AND logical_node_id=? AND origin_session_id=? AND event_sequence=?",
                            tuple(body["event_key"].values())).fetchone()[0], 1)
                        verification.close()
                        if attempts == 1:
                            status, authenticated, complete, response = 0, 0, 0, {}
                            failures += 1  # Backend committed, reply lost.
                        elif attempts == 2:
                            response["event_key"] = dict(response["event_key"], physical_device_id="other-device")
                            failures += 1
                        elif attempts == 3:
                            complete = 0  # Response framing truncated after commit.
                            failures += 1
                    process.stdin.write(f"{status} {authenticated} {complete}\n")
                    process.stdin.write(json.dumps(response, separators=(",", ":")) + "\n")
                    process.stdin.flush()
                    attempts += 1
                    if attempts % 100 == 0:
                        db.close(); db = connect(); endpoint = api(); restarts += 1
                self.assertEqual(process.wait(timeout=15), 0, process.stderr.read())
            finally:
                selector.close()
                if process.poll() is None:
                    process.kill(); process.wait(timeout=5)
                process.stdin.close(); process.stdout.close(); process.stderr.close()
            self.assertEqual(len(original), 300)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 300)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM durable_event_commits").fetchone()[0], 300)
            for table in ["alerts", "notification_jobs", "durable_notification_outbox"]:
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 30)
            self.assertGreaterEqual(duplicates, 3)
            self.assertEqual(failures, 4)
            db.close()
            print(output, f"backend_restarts={restarts} backend_duplicates={duplicates}",
                  f"fixture_failures={failures} wall_seconds={time.monotonic() - start:.3f}")


if __name__ == "__main__":
    unittest.main()
