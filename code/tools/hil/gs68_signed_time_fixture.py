"""Ephemeral host signer for the isolated GS-68 TEST_ONLY signed-time probe.

This module never opens a device or writes key material. Its RSA private key
exists only in the current Python process and is discarded when it exits.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

CASE_ID = "GS68-AUX-TIME-001"
SIGNED_TIME_CASE_IDS = {"GS68-AUX-TIME-001", "GS68-AUX-TIME-002"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ZERO_NONCE = "0" * 64


class SignedTimeFixtureError(ValueError):
    pass


class TestOnlySignedTimeFixture:
    """Build command payloads for the external-key target verification path."""

    def __init__(self):
        self.__private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)

    def load_key_command(self) -> dict[str, str]:
        public_der = self.__private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return {
            "schema": "gs68.target.command.v1",
            "case_id": CASE_ID,
            "challenge_nonce": ZERO_NONCE,
            "operation": "LOAD_TIME_KEY",
            "payload_b64": base64.b64encode(public_der).decode("ascii"),
        }

    def proof_command(self, challenge_frame: dict, *, issued_at_utc: int | None = None) -> dict[str, str]:
        if (not isinstance(challenge_frame, dict) or
                challenge_frame.get("schema") != "gs68.target.event.v1" or
                challenge_frame.get("event") != "time_challenge" or
                challenge_frame.get("case_id") not in SIGNED_TIME_CASE_IDS):
            raise SignedTimeFixtureError("target time challenge frame is invalid")
        nonce = challenge_frame.get("challenge_nonce")
        generation = challenge_frame.get("boot_generation")
        if (not isinstance(nonce, str) or not HEX64.fullmatch(nonce) or
                not isinstance(generation, int) or isinstance(generation, bool) or generation <= 0):
            raise SignedTimeFixtureError("target nonce or boot generation is invalid")
        issued = int(time.time()) if issued_at_utc is None else issued_at_utc
        if not isinstance(issued, int) or isinstance(issued, bool) or issued <= 0:
            raise SignedTimeFixtureError("TEST_ONLY issued time must be a positive integer")
        valid_from = issued
        valid_until = issued + 120
        proof_generation = generation
        if isinstance(challenge_frame.get("proof_variant"), dict):
            variant = challenge_frame["proof_variant"]
            issued = variant.get("issued_at_utc", issued)
            valid_from = variant.get("valid_from_utc", issued)
            valid_until = variant.get("valid_until_utc", issued + 120)
            proof_generation = variant.get("boot_generation", generation)
            if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0
                   for v in (issued, valid_from, valid_until, proof_generation)):
                raise SignedTimeFixtureError("TEST_ONLY proof variant fields must be positive integers")
        if valid_until <= valid_from:
            raise SignedTimeFixtureError("TEST_ONLY proof interval is invalid")
        signed = (
            b"GSTP\x01\x01\x00\x00" + proof_generation.to_bytes(8, "big") +
            bytes.fromhex(nonce) + issued.to_bytes(8, "big") +
            valid_from.to_bytes(8, "big") + valid_until.to_bytes(8, "big")
        )
        if len(signed) != 72:
            raise SignedTimeFixtureError("signed-time payload has an invalid size")
        signature = self.__private_key.sign(signed, padding.PKCS1v15(), hashes.SHA256())
        proof = signed + signature
        if len(proof) != 456:
            raise SignedTimeFixtureError("signed-time proof has an invalid size")
        return {
            "schema": "gs68.target.command.v1",
            "case_id": challenge_frame["case_id"],
            "challenge_nonce": nonce,
            "operation": "TIME_PROOF",
            "payload_b64": base64.b64encode(proof).decode("ascii"),
        }


def _decode_challenge(line: str) -> dict:
    line = line.strip()
    if line.startswith("GS68/1 "):
        line = line[len("GS68/1 "):]
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise SignedTimeFixtureError("pasted target challenge is not JSON") from exc
    if not isinstance(value, dict):
        raise SignedTimeFixtureError("pasted target challenge is not an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issued-at-utc", type=int,
                        help="TEST_ONLY synthetic signed time; defaults to this host's clock")
    args = parser.parse_args()
    fixture = TestOnlySignedTimeFixture()
    print("TEST_ONLY_LOAD_TIME_KEY_COMMAND=" + json.dumps(
        fixture.load_key_command(), sort_keys=True, separators=(",", ":")))
    print("Send that command and TIME_CHALLENGE to the separately authorized target;"
          " paste only its time_challenge event here.", file=sys.stderr)
    try:
        challenge = _decode_challenge(sys.stdin.readline())
        command = fixture.proof_command(challenge, issued_at_utc=args.issued_at_utc)
    except (SignedTimeFixtureError, OverflowError) as exc:
        print(f"GS68_TEST_ONLY_TIME_FIXTURE=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("TEST_ONLY_TIME_PROOF_COMMAND=" + json.dumps(
        command, sort_keys=True, separators=(",", ":")))
    print("Private key stayed in process memory and was not written or printed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
