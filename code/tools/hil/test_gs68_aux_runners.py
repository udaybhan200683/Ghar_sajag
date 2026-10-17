from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import gs68_aux_diagnostic as aux
import gs68_capture as capture


class FakeTransport:
    def __init__(self, frames):
        self.frames = list(frames)
        self.writes = []
        self.opened = self.closed = False

    def open(self): self.opened = True
    def write(self, payload): self.writes.append(payload)
    def read_line(self, timeout): return self.frames.pop(0) if self.frames else b""
    def close(self): self.closed = True


def response(event="command_result", **extra):
    body = {"schema": "gs68.target.event.v1", "event": event, **extra}
    return capture.FRAME_PREFIX + capture.canonical_json(body) + b"\n"


class GS68AuxiliaryRunnerTests(unittest.TestCase):
    def test_case_ids_are_auxiliary_and_never_official(self):
        self.assertEqual(len(aux.AUX_CASES), 7)
        self.assertTrue(all(case.startswith("GS68-AUX-") for case in aux.AUX_CASES))
        self.assertNotIn("GS68-PHY-003", aux.AUX_CASES)
        result = aux.classify("PASS", "host simulation")
        self.assertEqual(result["qualification_scope"], "AUXILIARY_TEST_ONLY_ONLY")
        self.assertEqual(result["official_gs68_physical_acceptance"], "NOT_RUN")

    def test_command_is_bounded_nonce_bound_and_auxiliary_only(self):
        with self.assertRaises(aux.AuxiliaryDiagnosticError):
            aux.command_frame("GS68-PHY-003", nonce="a" * 64)
        with self.assertRaises(aux.AuxiliaryDiagnosticError):
            aux.command_frame("GS68-AUX-USB-001", nonce="A" * 64)
        frame = json.loads(aux.command_frame("GS68-AUX-USB-001", nonce="a" * 64))
        self.assertEqual(frame["challenge_nonce"], "a" * 64)
        self.assertLessEqual(len(aux.command_frame("GS68-AUX-USB-001", nonce="a" * 64)), 1024)

    def test_usb_command_sequence_requires_rejection_and_recovery(self):
        nonces = [f"{number:064x}" for number in range(1, 6)]
        transport = FakeTransport([
            response(case_id="GS68-AUX-USB-001", challenge_nonce=nonces[0], result="OBSERVED_NO_ACTION"),
            response("case_result", case_outcome="FAIL", reason="INVALID_OR_OVERSIZED_COMMAND"),
            response(case_id="GS68-AUX-USB-002", challenge_nonce=nonces[1], result="OBSERVED_NO_ACTION"),
            response("case_result", case_outcome="FAIL", reason="INVALID_OR_OVERSIZED_COMMAND"),
            response(case_id="GS68-AUX-USB-002", challenge_nonce=nonces[2], result="OBSERVED_NO_ACTION"),
            response(case_id="GS68-AUX-USB-003", challenge_nonce=nonces[3], result="OBSERVED_NO_ACTION"),
            response(case_id="GS68-AUX-USB-003", challenge_nonce=nonces[4], result="OBSERVED_NO_ACTION"),
        ])
        session = aux.BoundedAuxiliarySession(transport)
        session.open()
        try:
            with patch.object(aux.secrets, "token_hex", side_effect=nonces):
                rows = aux.run_usb_sequence(session, fragment_delay=0)
        finally:
            session.close()
        self.assertTrue(transport.closed)
        self.assertEqual([row["status"] for row in rows], ["PASS", "PASS", "PASS"])
        self.assertTrue(all(row["official_gs68_physical_acceptance"] == "NOT_RUN" for row in rows))
        self.assertEqual(len(transport.writes), 5)

    def test_unexpected_acceptance_of_invalid_input_is_fail(self):
        nonces = [f"{number:064x}" for number in range(1, 6)]
        transport = FakeTransport([response(result="OBSERVED_NO_ACTION"),
            response("case_result", case_outcome="PASS"), response(result="OBSERVED_NO_ACTION")])
        session = aux.BoundedAuxiliarySession(transport)
        session.open()
        with patch.object(aux.secrets, "token_hex", side_effect=nonces), patch.object(session, "read_frame", side_effect=[
                json.loads(response(case_id="GS68-AUX-USB-001", challenge_nonce=nonces[0], result="OBSERVED_NO_ACTION")[len(capture.FRAME_PREFIX):-1]),
                json.loads(response("case_result", case_outcome="PASS")[len(capture.FRAME_PREFIX):-1]),
                json.loads(response(result="OBSERVED_NO_ACTION")[len(capture.FRAME_PREFIX):-1])]):
            row = aux.run_usb_sequence(session, fragment_delay=0)
        session.close()
        self.assertEqual(row[-1]["status"], "FAIL")

    def test_timeout_disconnect_and_bad_prefix_never_pass(self):
        session = aux.BoundedAuxiliarySession(FakeTransport([]))
        session.open()
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "timeout"):
            session.read_frame(0.1)
        session.close()
        session = aux.BoundedAuxiliarySession(FakeTransport([b"other\n"]))
        session.open()
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "prefix"):
            session.read_frame()
        session.close()

    def test_bundle_hashes_records_and_cannot_promote_official_cases(self):
        bundle = aux.evidence_bundle(fixture_id="GS68-SPARE-001", source_commit="a" * 40,
            image_sha256="b" * 64, records=[aux.classify("BLOCKED", "inspection unavailable")])
        self.assertEqual(bundle["physical"], "AUXILIARY_TEST_ONLY_ONLY")
        self.assertEqual(bundle["official_gs68_physical_acceptance"], "NOT_RUN")
        self.assertEqual(len(bundle["records_sha256"]), 64)

    def test_unproven_fixture_install_gates_block_before_transport_creation(self):
        fixture = {"fixture_id": "GS68-SPARE-UNASSIGNED", "source_commit": "a" * 40,
                   "image": {"sha256": "b" * 64}}
        with patch.object(aux, "validate_candidate_binding", return_value=[]), \
             patch.object(aux, "PySerialTransport", side_effect=AssertionError("serial opened"),
                          create=True):
            result = aux.execute_usb_if_ready(fixture, {}, repo=__import__("pathlib").Path("."))
        self.assertEqual(result["physical"], "AUXILIARY_TEST_ONLY_ONLY")
        self.assertEqual(result["official_gs68_physical_acceptance"], "NOT_RUN")
        self.assertTrue(all(row["status"] == "BLOCKED" for row in result["records"]))

    def test_missing_identity_target_preflight_never_constructs_http_request(self):
        from pathlib import Path
        source = Path(__file__).parents[2] / "firmware/hub/target/esp32s3/idf/gs68_cloudsync_diagnostic/app_main.cpp"
        body = source.read_text()
        start = body.index("void handle_missing_identity_case(")
        end = body.index("void handle_time_key(", start)
        handler = body[start:end]
        self.assertNotIn("channel.post", handler)
        self.assertIn("network_attempted=false", handler)
        self.assertIn("UnprovisionedS3CloudTrust", handler)


if __name__ == "__main__":
    unittest.main()
