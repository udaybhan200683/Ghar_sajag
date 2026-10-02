"""Deterministic architecture model for the proposed Node retirement report.

This is deliberately separate from production firmware. It proves the state
rules that a future Node/Hub implementation must preserve.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hmac
import struct
import unittest


MAX_PENDING = 32
MAX_HUB_KEYS = 128
EPOCH = 7
SECRET = b"retirement-model-key"


@dataclass(frozen=True, order=True)
class Key:
    session: int
    sequence: int


@dataclass(frozen=True)
class Snapshot:
    session: int
    highwater: int
    # Kind is durable with the retry payload. Heartbeat is sequenced too.
    pending: tuple[tuple[Key, bytes, str], ...]
    generation: int


@dataclass(frozen=True)
class Report:
    epoch: int
    generation: int
    current_session: int
    highwater: int
    outstanding: tuple[Key, ...]

    def encode(self) -> bytes:
        assert 0 <= len(self.outstanding) <= MAX_PENDING
        assert self.outstanding == tuple(sorted(set(self.outstanding)))
        return struct.pack(">BIQQQB", 1, self.epoch, self.generation,
                           self.current_session, self.highwater,
                           len(self.outstanding)) + b"".join(
            struct.pack(">QQ", k.session, k.sequence) for k in self.outstanding)

    def digest(self) -> bytes:
        return hmac.digest(SECRET, b"GS-RETIRE-REPORT-v1\0" + self.encode(),
                           "sha256")


def event_digest(key: Key, payload: bytes, kind: str = "business") -> bytes:
    return hmac.digest(SECRET, b"GS-EVENT-v1\0" +
                       struct.pack(">QQI", key.session, key.sequence,
                                   len(payload)) + kind.encode() + b"\0" + payload,
                       "sha256")


class Node:
    def __init__(self, session: int):
        self.session = session
        self.transport_session = session
        self.next_sequence = 1
        self.highwater = 0
        self.pending: dict[Key, tuple[bytes, str]] = {}
        self.durable = Snapshot(session, 0, (), 1)

    def persist(self) -> None:
        self.durable = Snapshot(self.session, self.highwater,
                                tuple(sorted((key, payload, kind)
                                             for key, (payload, kind) in self.pending.items())),
                                self.durable.generation + 1)

    def record(self, payload: bytes, *, admit: bool = True,
               persist: bool = True, kind: str = "business") -> Key | None:
        assert kind in ("business", "heartbeat")
        key = Key(self.session, self.next_sequence)
        self.next_sequence += 1  # Current firmware allocates before admission.
        if not admit or len(self.pending) == MAX_PENDING:
            return None
        self.pending[key] = (payload, kind)
        # Every admitted sequenced NodeMessage can enter the Hub journal.
        self.highwater = key.sequence
        if persist:
            self.persist()  # Target saves before radio send.
        return key

    def transmit(self, key: Key) -> bytes:
        return {saved: payload for saved, payload, _ in self.durable.pending}[key]

    def kind(self, key: Key) -> str:
        return {saved: kind for saved, _, kind in self.durable.pending}[key]

    def retire(self, key: Key, *, persist: bool = True) -> None:
        del self.pending[key]
        if persist:
            self.persist()

    def report(self) -> Report:
        s = self.durable
        return Report(EPOCH, s.generation, s.session, s.highwater,
                      tuple(sorted(k for k, _, _ in s.pending)))

    def reboot(self, new_session: int, *, persist: bool = True) -> None:
        assert new_session > self.transport_session
        s = self.durable
        self.pending = {key: (payload, kind) for key, payload, kind in s.pending}
        self.session = new_session
        self.transport_session = new_session
        self.next_sequence = 1
        self.highwater = 0
        if persist:
            self.persist()  # Baseline before a report/new admission.

    def rejoin(self, transport_session: int) -> None:
        assert transport_session > self.transport_session
        self.transport_session = transport_session
        # In-place rejoin leaves NodeRuntime's origin session unchanged.


class Hub:
    def __init__(self):
        self.report: Report | None = None
        self.committed: dict[Key, bytes] = {}
        self.durable: tuple[Report | None, dict[Key, bytes]] = (None, {})

    def event(self, key: Key, payload: bytes, *, kind: str = "business") -> str:
        assert kind in ("business", "heartbeat")
        report = self.report
        if report:
            if key.session > report.current_session:
                return "stale"
            known_at_report = (key.session < report.current_session or
                               key.sequence <= report.highwater)
            if known_at_report and key not in report.outstanding:
                return "stale"
        digest = event_digest(key, payload, kind)
        if key in self.committed:
            return "duplicate" if self.committed[key] == digest else "conflict"
        if len(self.committed) == MAX_HUB_KEYS:
            return "full"
        self.committed[key] = digest
        self.persist()
        return "new"

    def accept_report(self, report: Report, transport_session: int) -> str:
        keys = report.outstanding
        if (report.epoch != EPOCH or report.generation == 0 or
            report.current_session == 0 or
            report.current_session > transport_session or
            len(keys) > MAX_PENDING or keys != tuple(sorted(set(keys))) or
            any(k.session == 0 or k.sequence == 0 or
                k.session > report.current_session or
                (k.session == report.current_session and
                 k.sequence > report.highwater) for k in keys)):
            return "invalid"
        previous = self.report
        if previous:
            if report.generation < previous.generation:
                return "old"
            if report.generation == previous.generation:
                return ("duplicate" if report.digest() == previous.digest()
                        else "conflict")
            if (report.current_session < previous.current_session or
                (report.current_session == previous.current_session and
                 report.highwater < previous.highwater)):
                return "invalid"
            old_keys = set(previous.outstanding)
            for key in keys:
                previously_allocated = (
                    key.session < previous.current_session or
                    (key.session == previous.current_session and
                     key.sequence <= previous.highwater))
                if previously_allocated and key not in old_keys:
                    return "resurrected"
        self.report = report
        active = set(keys)
        self.committed = {
            key: digest for key, digest in self.committed.items()
            if key in active or (key.session == report.current_session and
                                 key.sequence > report.highwater)
        }
        self.persist()  # Durable before report response or forgetting keys.
        return "accepted"

    def persist(self) -> None:
        self.durable = (self.report, dict(self.committed))

    def reboot(self) -> None:
        self.report, saved = self.durable
        self.committed = dict(saved)


class RetirementProtocolModelTest(unittest.TestCase):
    def pair(self) -> tuple[Node, Hub]:
        return Node(10), Hub()

    def test_01_lost_ack_exact_duplicate(self):
        n, h = self.pair(); k = n.record(b"N")
        self.assertEqual(h.event(k, n.transmit(k)), "new")
        self.assertEqual(h.event(k, n.transmit(k)), "duplicate")

    def test_02_newer_event_before_older(self):
        n, h = self.pair(); a = n.record(b"a"); b = n.record(b"b")
        self.assertEqual(h.event(b, n.transmit(b)), "new")
        self.assertEqual(h.event(a, n.transmit(a)), "new")

    def test_03_floor_cannot_cross_pending(self):
        n, h = self.pair(); a = n.record(b"a"); b = n.record(b"b")
        self.assertEqual(h.event(b, n.transmit(b)), "new")
        n.retire(b)
        self.assertEqual(h.accept_report(n.report(), n.transport_session), "accepted")
        self.assertEqual(n.report().outstanding, (a,))
        self.assertEqual(h.event(a, n.transmit(a)), "new")
        self.assertEqual(h.event(b, b"b"), "stale")

    def test_04_gap_never_pins_retirement(self):
        n, h = self.pair(); a = n.record(b"a")
        self.assertIsNone(n.record(b"dropped", admit=False))
        c = n.record(b"c")
        self.assertEqual((a.sequence, c.sequence), (1, 3))
        n.retire(a); n.retire(c)
        self.assertEqual(h.accept_report(n.report(), n.transport_session), "accepted")
        self.assertEqual(h.event(Key(10, 2), b"ghost"), "stale")

    def test_05_node_reboot_preserves_old_key(self):
        n, h = self.pair(); k = n.record(b"a")
        n.reboot(11)
        self.assertIn(k, n.report().outstanding)
        self.assertEqual(h.event(k, n.transmit(k)), "new")

    def test_06_hub_reboot_preserves_duplicate(self):
        n, h = self.pair(); k = n.record(b"a")
        self.assertEqual(h.event(k, n.transmit(k)), "new")
        h.reboot()
        self.assertEqual(h.event(k, n.transmit(k)), "duplicate")

    def test_07_rejoin_changes_transport_only(self):
        n, h = self.pair(); k = n.record(b"a")
        n.rejoin(12)
        self.assertEqual(n.report().current_session, 10)
        self.assertEqual(h.accept_report(n.report(), n.transport_session), "accepted")
        self.assertEqual(h.event(k, n.transmit(k)), "new")

    def test_08_old_origin_after_new_origin(self):
        n, h = self.pair(); old = n.record(b"old")
        n.reboot(11); newer = n.record(b"new")
        self.assertEqual(h.event(newer, n.transmit(newer)), "new")
        self.assertEqual(h.event(old, n.transmit(old)), "new")

    def test_09_many_previous_sessions(self):
        n, h = self.pair()
        for session in range(10, 42):
            self.assertIsNotNone(n.record(str(session).encode()))
            n.reboot(session + 1)
        self.assertEqual(len(n.report().outstanding), 32)
        self.assertEqual(len({k.session for k in n.report().outstanding}), 32)
        self.assertEqual(h.accept_report(n.report(), n.transport_session), "accepted")

    def test_10_previous_session_closes(self):
        n, h = self.pair(); old = n.record(b"old")
        self.assertEqual(h.event(old, n.transmit(old)), "new")
        n.reboot(11); n.retire(old)
        self.assertEqual(h.accept_report(n.report(), n.transport_session), "accepted")
        self.assertNotIn(old, h.committed)
        self.assertEqual(h.event(old, b"old"), "stale")

    def test_11_delayed_old_report(self):
        n, h = self.pair(); k = n.record(b"a"); old = n.report()
        self.assertEqual(h.accept_report(old, 10), "accepted")
        n.retire(k)
        self.assertEqual(h.accept_report(n.report(), 10), "accepted")
        self.assertEqual(h.accept_report(old, 10), "old")

    def test_12_same_generation_conflict(self):
        n, h = self.pair(); n.record(b"a"); report = n.report()
        self.assertEqual(h.accept_report(report, 10), "accepted")
        self.assertEqual(h.accept_report(replace(report, highwater=99), 10), "conflict")

    def test_13_same_key_same_digest(self):
        n, h = self.pair(); k = n.record(b"same")
        self.assertEqual(h.event(k, b"same"), "new")
        self.assertEqual(h.event(k, b"same"), "duplicate")

    def test_14_same_key_different_digest(self):
        n, h = self.pair(); k = n.record(b"same")
        self.assertEqual(h.event(k, b"same"), "new")
        self.assertEqual(h.event(k, b"different"), "conflict")

    def test_15_crash_before_event_snapshot(self):
        n, _ = self.pair(); k = n.record(b"not-sent", persist=False)
        with self.assertRaises(KeyError): n.transmit(k)
        n.reboot(11)
        self.assertNotIn(k, n.report().outstanding)

    def test_16_crash_before_ack_retirement_snapshot(self):
        n, h = self.pair(); k = n.record(b"retry")
        self.assertEqual(h.event(k, n.transmit(k)), "new")
        n.retire(k, persist=False); n.reboot(11)
        self.assertEqual(h.event(k, n.transmit(k)), "duplicate")

    def test_17_crash_after_retirement_snapshot(self):
        n, h = self.pair(); k = n.record(b"done")
        self.assertEqual(h.event(k, n.transmit(k)), "new")
        n.retire(k); n.reboot(11)
        self.assertEqual(h.accept_report(n.report(), 11), "accepted")
        self.assertEqual(h.event(k, b"done"), "stale")

    def test_18_report_lost_then_retransmitted(self):
        n, h = self.pair(); n.record(b"a")
        report = n.report()  # First copy lost.
        self.assertEqual(h.accept_report(report, 10), "accepted")
        self.assertEqual(h.accept_report(report, 10), "duplicate")

    def test_19_hub_crash_before_report_response(self):
        n, h = self.pair(); n.record(b"a"); report = n.report()
        self.assertEqual(h.accept_report(report, 10), "accepted")
        h.reboot()
        self.assertEqual(h.accept_report(report, 10), "duplicate")

    def test_20_full_queue_and_wire_bound(self):
        n, h = self.pair()
        for i in range(MAX_PENDING): self.assertIsNotNone(n.record(bytes([i])))
        self.assertIsNone(n.record(b"overflow"))
        report = n.report()
        self.assertEqual(len(report.encode()), 30 + 16 * MAX_PENDING)
        self.assertEqual((len(report.encode()) + 169) // 170, 4)
        self.assertLessEqual(8 + 44 + 170 + 28, 250)
        self.assertEqual(h.accept_report(report, 10), "accepted")

    def test_21_resurrected_retired_key_rejected(self):
        n, h = self.pair(); k = n.record(b"a")
        n.retire(k)
        self.assertEqual(h.accept_report(n.report(), 10), "accepted")
        bad = replace(n.report(), generation=n.report().generation + 1,
                      outstanding=(k,))
        self.assertEqual(h.accept_report(bad, 10), "resurrected")

    def test_22_exact_storage_budget(self):
        checkpoint = 4253 - 10 * (1 + 64 + 1 + 24 + 8 + 8) + 32 * 40 + 41
        self.assertEqual(checkpoint, 4514)
        report_snapshot = 18 + 10 * (32 + 4 + 8 + 32 + 8 + 8 + 1 + 32 * 16) + 28
        self.assertEqual(report_snapshot, 6096)
        migration = (5328 + 2 * checkpoint + 16064 + 5040 + 768 + 512 +
                     checkpoint + 384 + 128 + 1004 + 40448)
        self.assertEqual(migration, 83218)
        self.assertGreaterEqual((131072 - migration) * 100, 131072 * 20)
        entries = 3160 + 3 * (9) + 34
        self.assertEqual(entries, 3221)
        self.assertGreaterEqual((4032 - entries) * 100, 4032 * 20)
        normal = 5328 + 2 * checkpoint + 32128 + 5040 + 768 + 512 + 6030 + 3 * report_snapshot
        self.assertEqual(normal, 77122)
        normal_entries = 3160 - 1792 - 544 + 1088 + 27 + 3 * (2 + (report_snapshot + 31) // 32) + 34
        self.assertEqual(normal_entries, 2552)
        independent_receipts = 128 * 32
        independent_entries = 128 * (2 + (32 + 31) // 32)
        self.assertEqual(migration + independent_receipts, 87314)
        self.assertEqual(131072 - migration - independent_receipts, 43758)
        self.assertEqual(entries + independent_entries, 3605)
        self.assertEqual(4032 - entries - independent_entries, 427)

    def test_23_heartbeat_between_business_events_is_reported(self):
        n, h = self.pair()
        n.next_sequence = 10
        first = n.record(b"business-10")
        heartbeat = n.record(b"heartbeat-11", kind="heartbeat")
        later = n.record(b"business-12")
        self.assertEqual((first.sequence, heartbeat.sequence, later.sequence),
                         (10, 11, 12))
        self.assertEqual(n.report().highwater, 12)
        self.assertEqual(n.report().outstanding, (first, heartbeat, later))
        self.assertEqual(h.event(heartbeat, n.transmit(heartbeat),
                                 kind=n.kind(heartbeat)), "new")
        self.assertEqual(h.accept_report(n.report(), n.transport_session), "accepted")
        self.assertEqual(h.event(heartbeat, n.transmit(heartbeat),
                                 kind=n.kind(heartbeat)), "duplicate")
        n.reboot(11)
        self.assertEqual(n.kind(heartbeat), "heartbeat")
        self.assertIn(heartbeat, n.report().outstanding)
        self.assertEqual(h.event(heartbeat, n.transmit(heartbeat),
                                 kind=n.kind(heartbeat)), "duplicate")

    def test_24_heartbeat_pending_after_business_drains(self):
        n, h = self.pair()
        n.next_sequence = 10
        first = n.record(b"business-10")
        intervening = n.record(b"heartbeat-11", kind="heartbeat")
        later = n.record(b"business-12")
        last = n.record(b"heartbeat-13", kind="heartbeat")
        for key in (first, intervening, later, last):
            self.assertEqual(h.event(key, n.transmit(key), kind=n.kind(key)), "new")
        for key in (first, intervening, later):
            n.retire(key)
        self.assertEqual(n.report().highwater, 13)
        self.assertEqual(n.report().outstanding, (last,))
        self.assertEqual(h.accept_report(n.report(), n.transport_session), "accepted")
        self.assertEqual(set(h.committed), {last})
        self.assertEqual(h.event(first, b"business-10"), "stale")
        self.assertEqual(h.event(later, b"business-12"), "stale")
        self.assertEqual(h.event(last, n.transmit(last), kind=n.kind(last)),
                         "duplicate")
        n.reboot(11)
        self.assertIn(last, n.report().outstanding)
        self.assertEqual(h.accept_report(n.report(), n.transport_session), "accepted")
        self.assertEqual(h.event(last, n.transmit(last), kind=n.kind(last)),
                         "duplicate")
        n.retire(last)
        self.assertEqual(h.accept_report(n.report(), n.transport_session), "accepted")
        self.assertNotIn(last, h.committed)
        self.assertEqual(h.event(last, b"heartbeat-13", kind="heartbeat"), "stale")


if __name__ == "__main__":
    unittest.main()
